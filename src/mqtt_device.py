class MqttDevice(object):

    def __init__(self, **kwargs):
        self.config: dict[str, str] = dict()
        for key, value in kwargs.items():
            self.config[key] = value

    def name(self, name: str):
        self.config["name"] = name

    def manufacturer(self, mfr: str):
        self.config["manufacturer"] = mfr

    def model(self, model: str):
        self.config["model"] = model

    def serial_number(self, serial: str):
        self.config["serial_number"] = serial

    def software_version(self, sw_version: str):
        self.config["sw_version"] = sw_version

    def hardware_version(self, hw_version: str):
        self.config["hw_version"] = hw_version

    def url(self, url: str):
        self.config["configuration_url"] = url

    def connections(self, connections: list[str]):
        self.config["connections"] = connections

    def identifiers(self, ids: list[str]):
        self.config["identifiers"] = list()
        for i in ids:
            self.config["identifiers"].append(i.lower().replace(' ', '-'))

    def get(self) -> dict[str, str]:
        return self.config

    def get_reference(self) -> dict[str, str]:
        dev: dict[str, str] = dict()
        if "identifiers" in self.config:
            dev["identifiers"] = self.config["identifiers"]
        if "connections" in self.config:
            dev["connections"] = self.config["connections"]
        return dev


def get_ref_device(device: MqttDevice) -> MqttDevice:
    dev: MqttDevice = MqttDevice()
    if "identifiers" in device.config:
        dev.config["identifiers"] = device.config["identifiers"]
    if "connections" in device.config:
        dev.config["connections"] = device.config["connections"]
    return dev
