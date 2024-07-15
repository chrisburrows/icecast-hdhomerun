import sys
import os
import logging
import argparse
import time
from process_runner import ProcessRunner
from mqtt_server import MqttServer
from mqtt_device import MqttDevice, get_ref_device
from mqtt_sensor import MqttSensor
from mqtt_select import MqttSelect
from mqtt_switch import MqttSwitch, ON, OFF
from hdhomerun import HdHomeRun
from icecast import Icecast
from config import Config

APP_NAME = "Radio Belstead"
ON: bool = True
OFF: bool = False


def enable_debug(enabled: bool) -> None:
    level = logging.DEBUG if enabled else logging.INFO
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.info("Logging level changed to {}".format("debug" if enabled else "info"))
    for handler in logger.handlers:
        if isinstance(handler, type(logging.StreamHandler())):
            handler.setLevel(level)


class Radio(MqttServer):
    _logger = logging.getLogger(__name__)

    ffmpeg_codec: dict[str, list[str]] = dict()

    ffmpeg_codec["flac"] = [
        '-c:a', 'flac',
        '-b:a', '192k',
        '-compression_level', '10',
        '-f', 'ogg',
        '-content_type', 'application/ogg'
    ]

    ffmpeg_codec["mp3"] = [
        '-c:a', 'libmp3lame',
        '-qscale:a', '3',
        '-f', 'mp3',
        '-content_type', 'audio/mpeg'
    ]

    ffmpeg_codec["aac"] = [
        '-c:a', 'aac',
        '-b:a', '192k',
        '-f', 'adts',
        '-content_type', 'audio/aac'
    ]

    device: MqttDevice = MqttDevice(name=APP_NAME,
                                    identifiers=[APP_NAME.lower().replace(' ', '-')],
                                    manufacturer="Chris Burrows",
                                    model="HD-HomeRun Icecast Streamer")

    ref_device: MqttDevice = get_ref_device(device)

    def __init__(self, config: Config):
        super().__init__(config.mqtt_config())
        self.listeners_zero_time: int = 0
        self.listeners_non_zero_time: int = 0
        self.codec: str = config.codec()
        self.ffmpeg: str = config.ffmpeg_path()
        self.proc: ProcessRunner = ProcessRunner(callback=self.process_state_change)
        self.icecast_idle_time: int = config.icecast_config()["idle_time"]
        self.source: str = None
        self.tuner: HdHomeRun = HdHomeRun(config.hdhomerun_config())
        self.icecast: Icecast = Icecast(config.icecast_config())

        # MQTT sensors and switches
        self.source_select: MqttSelect = MqttSelect(APP_NAME + " Station", self,
                                                    device=self.device, retain=True)
        self.playback: MqttSwitch = MqttSwitch(APP_NAME + " Playback", self, OFF,
                                               device=self.device, retain=True)
        self.playback_sensor: MqttSensor = MqttSensor(APP_NAME + " Sensor", self,
                                                      device=self.device, retain=True)
        self.idle_timeout_enable: MqttSwitch = MqttSwitch(APP_NAME + " Idle Timeout Enable", self,
                                                          OFF, device=self.device, retain=True)
        self.auto_start: MqttSwitch = MqttSwitch(APP_NAME + " Playback Auto Start", self, ON,
                                                 device=self.device, retain=True)
        self.debug: MqttSwitch = MqttSwitch(APP_NAME + " Debug Logging", self, ON,
                                            diagnostic=True, device=self.device, retain=True)

        # Bind MQTT callbacks
        self.playback.bind(self.on_off)
        self.source_select.bind(self.station)
        self.icecast.bind(self.icecast.get_icecast_listen_url(), self.listeners)
        self.tuner.bind(self._channels_update)
        self.debug.bind(enable_debug)
        self.playback_sensor.update("idle")

    def _channels_update(self, channels: list[str]) -> None:
        self._logger.debug("Channels updated")
        self.source_select.set_options(channels)

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        self._logger.debug("Radio on_connect")
        super().on_connect(client, userdata, flags, reason_code, properties)

    def on_off(self, is_on: bool) -> None:
        """Start / Stop command"""
        if is_on:
            if self.proc is None:
                self.play()
        else:
            if self.proc is not None:
                if self.proc.stop():
                    self.playback_sensor.update("idle")
                    self.proc = None
                else:
                    self.playback_sensor.update("error")
                    self.playback.update(OFF)

    def play(self) -> None:
        """Start playback"""

        if self.source is None:
            self._logger.debug("Not starting playback - no station selected")
            self.playback.update(OFF)
            self.playback_sensor.update("idle")
            return

        source_url = self.tuner.get_channel_url(self.source)
        if source_url is None:
            self._logger.error("Unknown radio station selected")
            self.source = None
            self.playback.update(OFF)
            self.playback_sensor.update("idle")
            return

        self._logger.debug(
            "Starting playback for {station} from {url}".format(
                station=self.source,
                url=source_url))

        ffmpeg_preamble = [
            '{ffmpeg}'.format(ffmpeg=self.ffmpeg),
            '-hide_banner',
            '-loglevel', 'panic',
            '-nostats',
            '-fflags', 'nobuffer',
            '-analyzeduration', '1000000',
            '-i', '{source}'.format(source=source_url),
            '-vn',
            '-map', '0:a:0',
            '-ar', '48000',
            '-ac', '2'
        ]

        ffmpeg_icecast = [
            '-ice_name', '{description}'.format(description=self.source),
            '-ice_description', '{description}'.format(description=self.tuner.get_channel_description(self.source)),
            'icecast://' + self.icecast.get_icecast_publish_url()
        ]

        ffmpeg = ffmpeg_preamble + self.ffmpeg_codec[self.codec] + ffmpeg_icecast

        self._logger.debug("FFMPEG command: {}".format(ffmpeg))
        self.proc.start(ffmpeg, restart=False)

    def stop(self):
        success = True
        if self.proc is not None and self.proc.is_running():
            self._logger.debug("Stopping existing stream for {}".format(self.source))
            success = self.proc.stop()
            if success:
                self.playback.update(OFF)
                self.playback_sensor.update("idle")
            else:
                self._logger.debug("Failed to stop existing stream: {}".format(self.source))
                self.playback_sensor.update("error")
        return success

    def station(self, station: str) -> None:
        """Process selection / change of playback station"""
        self._logger.debug("Station request: {}".format(station))

        stopped = True
        if self.source is not None and station.lower() == self.source.lower():
            if self.proc is not None and self.proc.is_running():
                self._logger.debug("Already streaming this station")
                return
        else:
            stopped = self.stop()

        if not stopped:
            return

        if self.tuner.get_channel_url(station) is not None:
            self.source = station
        else:
            self._logger.debug("Non existent station {}".format(station))
            self.playback_sensor.update("idle")
            return

        if self.playback.is_on() or self.auto_start.is_on():
            self.play()

    def listeners(self, station: str, count: int) -> None:
        """Process a change in the number of listeners"""

        self._logger.debug("Listeners {}".format(count))
        now = time.monotonic()
        if count == 0:
            if self.listeners_non_zero_time != 0:
                self.listeners_non_zero_time = 0
                self.listeners_zero_time = now

            if (self.idle_timeout_enable.is_on()
                    and self.listeners_zero_time > 0
                    and now - self.listeners_zero_time > self.icecast_idle_time):
                self.stop()

        else:
            if self.listeners_non_zero_time == 0:
                self.listeners_non_zero_time = now
                self.listeners_zero_time = 0

    def process_state_change(self, state: str, rc: int) -> None:
        """Handle subprocess (ffmpeg) state changes"""
        if state == "start":
            self.playback_sensor.update("playing")
            self.playback.update(ON)
        else:
            self.playback_sensor.update("idle")
            self.playback.update(OFF)

    def terminate(self):
        """Stop things and exit"""
        self._logger.debug("Stopping")
        if self.proc is not None:
            self.process.stop()
        sys.exit(0)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(
        prog="Local Radio Server",
        description="Serves radio stations from Hd-HomeRun via Icecast server controlled via MQTT"
    )
    parser.add_argument('-c', '--config', help="JSON configuration file", dest='config', default="config.json")
    args = parser.parse_args()

    try:
        configuration = Config(args.config)
        configuration.load()
        radio = Radio(configuration)
        radio.run()
    except KeyboardInterrupt:
        radio.stop()