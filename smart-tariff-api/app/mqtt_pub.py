import json
import paho.mqtt.client as mqtt

class MQTTPublisher:
    def __init__(self, host, port, username, password, prefix):
        self.prefix = prefix.rstrip("/")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self.client.username_pw_set(username, password or None)
        self.client.connect(host, port, keepalive=60)
           self.client.loop_start()  # <-- REQUIRED so publish() actually sends

    def pub(self, topic, payload):
        # ALWAYS publish under smartenergy/... regardless of config
        full = f"smartenergy/{topic.lstrip('/')}"
        try:
            self.client.publish(full, json.dumps(payload), qos=1, retain=True)
        except Exception as e:
            print(f"MQTT publish failed: {e}")
