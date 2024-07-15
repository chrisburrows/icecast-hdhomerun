import logging
import time
from typing import Callable
from mqtt_sensor import MqttBaseSensor
from mqtt_server import MqttServer
from mqtt_device import MqttDevice
from mqtt_base_sensor import HA_DISCOVERY_ROOT

HA_DISCOVERY_SELECT = HA_DISCOVERY_ROOT + "/select/"


class MqttSelect(MqttBaseSensor):
    _logger = logging.getLogger(__name__)

    def __init__(self, name: str, server: MqttServer, options: list[str] = list(),
                 device: MqttDevice = None,
                 retain: bool = False):
        super().__init__(name, server, HA_DISCOVERY_SELECT, device, retain)
        self.options: list[str] = options
        self.callback: Callable = None
        if options is not None and len(options) > 0:
            self._ha_discovery()

    def _ha_discovery(self) -> None:
        self.config["command_topic"] = self.name.replace(" ", "-").lower() + "/set"
        self.config["options"] = self.options
        self.config["retain"] = True
        self.mqtt.bind(self.config["command_topic"], self._mqtt_set)
        super()._ha_discovery()

    def _mqtt_set(self, topic: str, message: str) -> None:
        """Update selection from MQTT"""
        if message in self.options:
            super().update(message)
            if self.callback is not None:
                self.callback(message)

    def bind(self, callback: Callable) -> None:
        """Set the callback function for when selection is changed"""
        self.callback = callback

    def set_options(self, options: list) -> None:
        """Replace existing options with new ones"""
        self.options = options
        self._ha_discovery()

    def add_option(self, option: str) -> None:
        if option not in self.options:
            self.options.append(option)
        self._ha_discovery()

    def remove_option(self, option: str) -> None:
        if option in self.options:
            self.options.remove(option)
        self._ha_discovery()


if __name__ == '__main__':
    mqtt_config = {
        "host": "mqtt.home",
        "username": "monitor",
        "password": "7uGGEfryZqNk",
        "topic_root": "radio-hdhomerun"
    }

    logging.basicConfig(level=logging.DEBUG)
    server = MqttServer(mqtt_config)
    select = MqttSelect("test_select", server, ["one", "two", "three", "four"])

    server.run()

    time.sleep(999)