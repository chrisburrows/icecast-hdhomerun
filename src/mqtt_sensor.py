import logging
import time

from mqtt_server import MqttServer
from mqtt_device import MqttDevice
from mqtt_base_sensor import MqttBaseSensor
from mqtt_base_sensor import HA_DISCOVERY_ROOT

HA_DISCOVERY_SENSOR = HA_DISCOVERY_ROOT + "/sensor/"


class MqttSensor(MqttBaseSensor):
    def __init__(self, name: str, server: MqttServer, device: MqttDevice = None, retain: bool = False):
        super().__init__(name, server, HA_DISCOVERY_SENSOR, device, retain)
        self._ha_discovery()

