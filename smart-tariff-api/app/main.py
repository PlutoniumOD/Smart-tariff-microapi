from fastapi import FastAPI
app = FastAPI(title="Smart Tariff Micro‑API")

import json
import paho.mqtt.client as mqtt

class MQTTPublisher:
    def __init__(self, host, port, username, password, prefix):
        self.prefix = prefix.rstrip("/")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        if username:
            self.client.username_pw_set(username, password or None)
        self.client.connect(host, port, keepalive=60)

    def pub(self, topic, payload):
        full = f"{self.prefix}/{topic.lstrip('/')}"
        self.client.publish(full, json.dumps(payload), qos=0, retain=True)
