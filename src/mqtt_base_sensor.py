import logging
from mqtt_server import MqttServer
from mqtt_device import MqttDevice

HA_DISCOVERY_ROOT = "homeassistant"
ON: bool = True
OFF: bool = False


class MqttBaseSensor:
    _logger = logging.getLogger(__name__)

    def __init__(self, name: str, server: MqttServer, discovery_path: str,
                 device: MqttDevice = None, retain: bool = False):
        self.name: str = name
        self.discovery_path: str = discovery_path
        self.mqtt: MqttServer = server
        self.value: str = None
        self.config: dict = dict()
        self.retain: bool = retain
        if device is not None:
            self.config["device"] = device.get()

    def _ha_discovery(self):
        self.config["name"] = self.name
        self.config["availability_topic"] = "status"
        self.config["state_topic"] = self.name.replace(" ", "-").lower() + "/state"
        self.config["unique_id"] = self.name.replace(" ", "_").lower()
        self.mqtt.ha_discovery(self.discovery_path, self.config)

    def update(self, value: str) -> None:
        self.value = value
        self.mqtt.publish(topic=self.config["state_topic"], message=value, retain=self.retain)

    def get_value(self) -> None:
        return self.value

    def get_name(self) -> str:
        return self.name

    def retain(self, retain: bool) -> None:
        self.retain = retain
