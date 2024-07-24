import logging
import threading
from typing import Callable
import requests
import time
import os

UPDATE_INTERVAL = 86400


class HdHomeRun:
    _logger = logging.getLogger(__name__)

    def __init__(self, config: dict):
        self.url = ("{scheme}://{server}:{port}"
                    .format(scheme=config["scheme"], server=config["server"], port=config["port"]))
        # self.stream_url = "{scheme}}://{server}:{port}".format(server=config["server"], port=config["streaming_port"])

        self.wanted_channels = config['channels']
        self.channels: dict = dict()
        self.last_update: int = 0
        self.callback: Callable = None
        self.thread = threading.Thread(target=self.run)
        self.thread.start()

    def bind(self, callback: Callable) -> None:
        """Set the callback function called when the station list changes"""
        self.callback = callback

    def _update_channels(self):
        """Pull latest channel lineup from the tuner"""
        r = requests.get(self.url + "/lineup.json")
        if r.status_code == 200:
            tmp: dict = dict()
            for ch in r.json():
                # we only want Radio stations
                if "AudioCodec" in ch and "VideoCodec" not in ch and int(ch["GuideNumber"]) in self.wanted_channels:
                    tmp[ch["GuideName"]] = {"url": ch["URL"], "name": ch["GuideName"]}

            old_channels: list[str] = sorted(self.channels.keys())
            new_channels: list[str] = sorted(tmp.keys())
            if old_channels != new_channels and self.callback is not None:
                self.callback(new_channels)
            self.channels = tmp
            self.last_update = time.time()

    def get_channel_url(self, name: str):
        """Lookup channel URL in channels data"""
        self._logger.debug("Looking up channel {}".format(name))

        if name in self.channels:
            return self.channels[name]["url"]
        return None

    def get_channel_description(self, name: str):
        """Lookup channel description in channels data"""
        self._logger.debug("Looking up channel description {}".format(name))

        if name in self.channels:
            return name
        return None

    def run(self):
        while True:
            try:
                self._update_channels()
                time.sleep(UPDATE_INTERVAL)
            except IOError:
                self._logger.error("Error accessing HD HomeRun to fetch channels data")
                time.sleep(UPDATE_INTERVAL)
