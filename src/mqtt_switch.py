import logging
import time
from typing import Callable
from mqtt_device import MqttDevice
from mqtt_server import MqttServer
from mqtt_base_sensor import MqttBaseSensor, HA_DISCOVERY_ROOT, ON, OFF

HA_DISCOVERY_SWITCH = HA_DISCOVERY_ROOT + "/switch/"


class MqttSwitch(MqttBaseSensor):
    logger = logging.getLogger(__name__)

    def __init__(self, name: str, server: MqttServer, initial_state: bool = OFF, diagnostic: bool = False,
                 device: MqttDevice = None, retain: bool = False):
        super().__init__(name, server, HA_DISCOVERY_SWITCH, device, retain)
        self._is_diagnostic = diagnostic
        self._ha_discovery()
        self.update(initial_state)
        self.callback: Callable = None
        server.bind(self.config["command_topic"], self._mqtt_set)

    def _ha_discovery(self):
        self.config["command_topic"] = self.name.replace(" ", "-").lower() + "/set"
        self.config["payload_on"] = "on"
        self.config["payload_off"] = "off"
        self.config["entity_category"] = "diagnostic" if self._is_diagnostic else "config"
        super()._ha_discovery()

    def bind(self, callback: Callable) -> None:
        """Set callback function for mqtt switch"""
        self.callback = callback

    def _mqtt_set(self, topic: str, payload: str):
        """Handle set on / off from MQTT"""
        super().update(payload)
        if self.callback is not None:
            self.callback(self.value == "on")

    def update(self, value: bool) -> None:
        """Get / set status"""
        super().update("on" if value else "off")

    def is_on(self) -> bool:
        return self.value == "on"

if __name__ == "__main__":
    mqtt_config = {
        "host": "mqtt.home",
        "username": "monitor",
        "password": "7uGGEfryZqNk",
        "topic_root": "radio-hdhomerun"
    }

    logging.basicConfig(level=logging.DEBUG)
    server = MqttServer(mqtt_config)
    switch = MqttSwitch("test_switch", "test_switch", server)
    switch2 = MqttSwitch("test_switch2", "test_switch2", server)

    server.run()

    time.sleep(9999)
