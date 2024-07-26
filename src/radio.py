import subprocess
import sys
import logging
import argparse
import time
from subprocess import Popen
from pipe_writer import PipeWriter
from ffmpeg import FFmpeg
from process_runner import ProcessRunner
from process_state import ProcessState
from mqtt_server import MqttServer
from mqtt_device import MqttDevice, get_ref_device
from mqtt_sensor import MqttSensor
from mqtt_select import MqttSelect
from mqtt_switch import MqttSwitch, ON, OFF
from hdhomerun import HdHomeRun
from icecast import Icecast
from config import Config
import hifi_berry

ON: bool = True
OFF: bool = False

logger = logging.getLogger(__name__)

# static reference to FFMPEG executable and config strings
ffmpeg: FFmpeg = FFmpeg()


def enable_debug(enabled: bool) -> None:
    level = logging.DEBUG if enabled else logging.INFO
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.info("Logging level changed to {}".format("debug" if enabled else "info"))
    for handler in logger.handlers:
        if isinstance(handler, type(logging.StreamHandler())):
            handler.setLevel(level)


class Radio(MqttServer):
    APP_NAME = "Radio Belstead"
    OUTPUT_OWNTONE = "Owntone"
    OUTPUT_ICECAST = "Icecast"
    OWNTONE_CODEC = "s16le"

    _logger = logging.getLogger(__name__)

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
        self.owntone_output: PipeWriter = None
        self.owntone_pipe: str = config.owntone_pipe()
        self.icecast_idle_time: int = config.icecast_config()["idle_time"]
        self.source: str = None
        self.tuner: HdHomeRun = HdHomeRun(config.hdhomerun_config())
        self.icecast: Icecast = Icecast(config.icecast_config())
        self.ffmpeg: FFmpeg = FFmpeg(config.ffmpeg_path())
        self.ffmpeg_proc: ProcessRunner = ProcessRunner(callback=self._process_state_change)

        # MQTT sensors and switches
        self.output_select: MqttSelect = MqttSelect(self.APP_NAME + " Output", self,
                                                    device=self.device, retain=True)
        self.source_select: MqttSelect = MqttSelect(self.APP_NAME + " Station", self,
                                                    device=self.device, retain=True)
        self.playback: MqttSwitch = MqttSwitch(self.APP_NAME + " Playback", self, OFF,
                                               device=self.device, retain=True)
        self.playback_sensor: MqttSensor = MqttSensor(self.APP_NAME + " Sensor", self,
                                                      device=self.device, retain=True)
        self.idle_timeout_enable: MqttSwitch = MqttSwitch(self.APP_NAME + " Idle Timeout Enable", self,
                                                          OFF, device=self.device, retain=True)
        self.auto_start: MqttSwitch = MqttSwitch(self.APP_NAME + " Playback Auto Start", self, ON,
                                                 device=self.device, retain=True)
        self.debug: MqttSwitch = MqttSwitch(self.APP_NAME + " Debug Logging", self, ON,
                                            diagnostic=True, device=self.device, retain=True)

        self.output_select.set_options([self.OUTPUT_OWNTONE, self.OUTPUT_ICECAST])

        # Bind MQTT callbacks
        self.playback.bind(self.on_off)
        self.source_select.bind(self.station)
        self.icecast.bind(self.icecast.get_icecast_listen_url(), self.listeners)
        self.tuner.bind(self._channels_update)
        self.debug.bind(enable_debug)
        self.playback_sensor.update("idle")

    def _channels_update(self, channels: list[str]) -> None:
        self._logger.debug("Channels updated")
        self.source_select.set_options(["HiFi"] + channels)

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        self._logger.debug("Radio on_connect")
        super().on_connect(client, userdata, flags, reason_code, properties)

    def on_off(self, is_on: bool) -> None:
        """Start / Stop command from MQTT"""
        if is_on:
            self.play()
        else:
            self.stop()

    def play(self) -> None:
        """Start playback"""

        if self.source is None:
            self._logger.debug("Not starting playback - no station selected")
            self.playback.update(OFF)
            self.playback_sensor.update("idle")
            return

        ffmpeg_command = self.ffmpeg.preamble()

        if self.source == "HiFi":
            ffmpeg_command = ffmpeg_command + self.ffmpeg.hifiberry_input()
            input_description = "HiFi"
        else:
            source_url = self.tuner.get_channel_url(self.source)
            input_description = self.tuner.get_channel_description(self.source)
            if source_url is None:
                self._logger.error("Unknown radio station selected")
                self.source = None
                self.playback.update(OFF)
                self.playback_sensor.update("idle")
                return
            ffmpeg_command = ffmpeg_command + self.ffmpeg.url_input(source_url)

        if self.output_select.get_value() == self.OUTPUT_ICECAST:
            ffmpeg_command = (ffmpeg_command
                              + self.ffmpeg.codec(self.codec)
                              + self.ffmpeg.icecast_output(self.source,
                                                           input_description,
                                                           self.icecast.get_icecast_publish_url())
                              )
            need_stdout = False

        else:
            ffmpeg_command = (ffmpeg_command
                              + self.ffmpeg.codec(self.OWNTONE_CODEC)
                              + self.ffmpeg.pipe_output())
            need_stdout = True

        self._logger.debug(
            "Starting playback for {station}".format(station=self.source))

        self._logger.debug("FFMPEG command: {}".format(ffmpeg))
        self.ffmpeg_proc.start(ffmpeg_command, restart=False, stdout=need_stdout)

    def stop(self):
        """Stop the streaming processes"""

        success = True
        sensor_value = "idle"
        self.playback.update(OFF)

        # stop the FFMPEG process first so the pipe-writer (if there is one) is still reading from ffmpeg's STDOUT
        # to ensure any kill signals don't fail because ffmpeg is blocked writing to it's output pipe
        if self.ffmpeg_proc.is_running():
            self._logger.debug("Stopping existing stream for {}".format(self.source))
            success = self.ffmpeg_proc.stop()
            if success:
                self._logger.debug("Stopped existing stream for {}".format(self.source))
            else:
                sensor_value = "ffmpeg error"
                self._logger.debug("Failed to stop existing stream: {}".format(self.source))

        #if self.owntone_output is not None:
        #    self._logger.debug("Stopping owntone pipe writer")
        #    self.owntone_output.stop()
        #    self.owntone_output.wait()
        #    self.owntone_output = None
        #    self._logger.debug("Stopped owntone pipe writer")

        self.playback_sensor.update(sensor_value)
        return success

    def station(self, station: str) -> None:
        """Process selection / change of playback station"""
        self._logger.debug("Station request: {}".format(station))

        stopped = True
        if self.source is not None and station.lower() == self.source.lower():
            if self.ffmpeg_proc is not None and self.ffmpeg_proc.is_running():
                self._logger.debug("Already streaming this station")
                return
        else:
            stopped = self.stop()

        if not stopped:
            return

        if station == "HiFi":
            self.source = station
        else:
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

    def _owntone_output_state_change(self, state: ProcessState, rc: int) -> None:
        """Handle subprocess (ffmpeg) state changes"""
        if state == ProcessState.STARTED:
            self.playback_sensor.update("playing")
            self.playback.update(ON)
        else:
            self.playback_sensor.update("idle")
            self.playback.update(OFF)
            if self.ffmpeg_proc is not None:
                self.ffmpeg_proc.stop()
                self.ffmpeg_proc.wait()
            self.owntone_output = None

    def _process_state_change(self, state: ProcessState, rc: int) -> None:
        """Handle subprocess (ffmpeg) state changes"""
        if state == ProcessState.STARTED:
            logging.debug("Process state change for STARTED")
            self.playback.update(ON)
            destination = "icecast"

            if self.output_select.get_value() == self.OUTPUT_OWNTONE:
                destination = "owntone"
                self.owntone_output = PipeWriter(self.ffmpeg_proc.get_stdout(), self.owntone_pipe)
                if not self.owntone_output.is_running():
                    self.stop()

            self.playback_sensor.update("playing " + destination)

        else:
            logging.debug("Process state change for STOPPED")
            status = "idle"
            if self.output_select.get_value() == self.OUTPUT_OWNTONE:
                if self.owntone_output is not None:
                    if not self.owntone_output.is_running():
                        status = "owntone error"
                    self.owntone_output.stop()
                    self.owntone_output.wait()
                    self.owntone_output = None
                else:
                    status = "pipe writer error"
            self.playback_sensor.update(status)
            self.playback.update(OFF)

    def terminate(self):
        """Stop things and exit"""
        self._logger.debug("Stopping")
        if self.ffmpeg_proc is not None:
            self.process.stop()
        if self.owntone_output is not None:
            self.owntone_output.stop()
        sys.exit(0)

    def hifi(self):
        """Launch input from HiFi Berry and write to Owntone"""

        ffmpeg = FFmpeg()
        ffmpeg_transcode = ffmpeg.preamble() + ffmpeg.pipe_input() + ffmpeg.pipe_input()

        owntone_pipe = open("audio_pipe", "wb")

        hifi = Popen(hifi_berry.hifi_berry(), stdin=subprocess.PIPE)
        transcode = Popen(ffmpeg_transcode, stdin=hifi.stdout, stdout=subprocess.PIPE)

        owntone = PipeWriter(transcode.stdout, owntone_pipe)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s %(levelname)s %(module)s:%(funcName)s %(message)s")

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
