import logging
import json
import paho.mqtt.client as mqtt


class MqttConfigError(Exception):
    def __init__(self, text: str) -> None:
        super().__init__(text)


class _MqttMessage(object):
    def __init__(self, topic: str, message: str, qos: int = 0, retain: bool = False) -> None:
        self._topic = topic
        self._message = message
        self._qos = qos
        self._retain = retain


class MqttServer(object):
    _logger = logger = logging.getLogger(__name__)
    _default_broker: str = "mqtt.home"
    _default_username: str = "mqtt"
    _default_password: str = "mqtt"
    _default_port: int = 1883
    _default_status_topic: str = "status"

    def __init__(self, config: dict):
        self._client: mqtt.Client = None
        self._bindings: dict = dict()
        self._message_queue = list()
        self._broker = config.get("host", self._default_broker)
        self._username = config.get("username", self._default_username)
        self._password = config.get("password", self._default_password)
        self._port = config.get("port", self._default_port)
        self._client_id = config.get("client_id", "mqtt_client")
        self._debug = config.get("debug", False)
        self.topic_root = config.get("base_topic").lower()
        if self.topic_root[-1] != "/":
            self.topic_root += "/"
        self.status_topic = self.topic_root + self._default_status_topic

        self.validate()

    def validate(self) -> None:
        """Validate some key config settings"""
        if self._client_id is None:
            raise MqttConfigError("Missing client_id")
        if self.topic_root is None:
            raise MqttConfigError("Missing topic_root")

    def _ha_base_path(self, config: dict(), key: str) -> None:
        if key in config and not config[key].startswith(self.topic_root):
            config[key] = self.topic_root + config[key]

    def ha_discovery(self, discovery_path: str, config: dict) -> None:
        """Publish an HA discovery message"""
        for key in ["state_topic", "command_topic", "availability_topic"]:
            self._ha_base_path(config, key)
        config["payload_available"] = "online"
        config["payload_not_available"] = "offline"

        self._publish(discovery_path.lower() + str(config["unique_id"]).lower() + "/config",
                      json.dumps(config),
                      retain=True)

    def get_topic_root(self) -> str:
        return self.topic_root

    def get_status_topic(self) -> str:
        return self.status_topic

    def connect(self) -> None:
        """Connect to MQTT broker"""
        self._logger.debug("Connecting to MQTT broker")
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._client_id)
        if self._username:
            self._client.username_pw_set(self._username, self._password)
        self._client.on_connect = self.on_connect
        self._client.on_connect_fail = self.connect_fail
        self._client.on_message = self.on_message
        self._client.on_disconnect = self.on_disconnect
        self._client.will_set(self.status_topic, "offline", qos=1, retain=True)
        if self._debug:
            self._client.enable_logger()

        self._client.connect(self._broker, self._port)

    def connect_fail(self) -> None:
        """Called when a failure occurs during the connection to the MQTT broker"""
        self._logger.debug("MQTT connection failed")

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        """Called after a successful connection"""
        if reason_code.is_failure:
            self.logger.error("Failed to connect to MQTT broker")
            return

        self.logger.debug("Connected to MQTT broker")
        self.publish(self.status_topic, "online", qos=1, retain=True)
        self.subscribe()

        for msg in self._message_queue:
            self._client.publish(msg._topic,
                                msg._message,
                                qos=msg._qos,
                                retain=msg._retain)
        self._message_queue.clear()

    def on_message(self, client, userdata, message) -> None:
        """Called for each message received from MQTT"""
        self._logger.debug("Message received on {} payload {}".format(message.topic, message.payload))
        callback = self._bindings.get(message.topic)
        if callback:
            callback(message.topic, message.payload.decode("utf-8"))

    def on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties) -> None:
        self._logger.debug("Disconnected from MQTT broker {}".format(reason_code))

    def subscribe(self):
        """Subscribe to the required topics"""
        self._logger.debug("Subscribing to topics")
        for topic in self._bindings.keys():
            rc = self._client.subscribe(topic)
            self.logger.debug("Subscribing to topic {} = {}".format(topic, rc))

    def _publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """Publish a message to a topic"""
        #self._logger.debug("Publishing {payload} to topic {topic}".format(payload=payload, topic=topic))
        if self._client is not None and self._client.is_connected():
            self._client.publish(topic, payload, qos=qos, retain=retain)
        else:
            self._message_queue.append(_MqttMessage(topic, payload, qos, retain))

    def publish(self, topic: str, message: str, qos: int = 0, retain: bool = False):
        if topic.startswith(self.topic_root):
            self._publish(topic, message, qos, retain)
        else:
            self._publish(self.topic_root + topic, message, qos, retain)

    def bind(self, topic: str, callback):
        """Bind messages on a topic to a callback function"""
        self._logger.debug("Binding: {}".format(topic))
        if topic.startswith(self.topic_root):
            topic_path = topic
        else:
            topic_path = self.topic_root + topic
        self._bindings[topic_path] = callback
        if self._client is not None and self._client.is_connected():
            self._client.subscribe(topic_path)

    def run(self):
        """Run the server forever processing MQTT messages"""
        self._logger.debug("Starting MQTT server")
        if self._client is None:
            self.connect()

        # self._client.loop_forever()
        self._client.loop_start()
