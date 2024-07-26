import logging
import time
from mqtt_server import MqttServer
from mqtt_device import MqttDevice
from mqtt_base_sensor import MqttBaseSensor, HA_DISCOVERY_ROOT, ON, OFF

HA_DISCOVERY_BINARY_SENSOR = HA_DISCOVERY_ROOT + "/binary_sensor/"


class MqttBinarySensor(MqttBaseSensor):

    def __init__(self, name: str, mqtt_server: MqttServer, initial_state: bool = OFF, device: MqttDevice = None):
        self._callback = None
        super().__init__(name, mqtt_server, HA_DISCOVERY_BINARY_SENSOR, device)
        self._ha_discovery()
        self.update(initial_state)

    def _ha_discovery(self):
        self.config["payload_on"] = "on"
        self.config["payload_off"] = "off"
        super()._ha_discovery()

    def update(self, value: bool):
        super().update("on" if value else "off")

    def get_value(self) -> bool:
        if self.value is not None:
            return super().get_value().lower() == "on"
        return False


