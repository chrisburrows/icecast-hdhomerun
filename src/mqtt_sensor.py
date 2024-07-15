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

if __name__ == "__main__":
    mqtt_config = {
        "host": "mqtt.home",
        "username": "monitor",
        "password": "7uGGEfryZqNk",
        "topic_root": "radio-hdhomerun"
    }

    logging.basicConfig(level=logging.DEBUG)
    server = MqttServer(mqtt_config)
    sensor = MqttSensor("test_sensor", "test_sensor", server)
    sensor2 = MqttSensor("test_sensor2", "test_sensor2", server)

    server.run()

    sensor.update("hello")
    sensor2.update("goodbye")

    time.sleep(15)
    sensor.update("world")
    sensor2.update("all")

    time.sleep(9999)

