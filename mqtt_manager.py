import traceback
import paho.mqtt.client as mqtt
from paho.mqtt.client import topic_matches_sub

class MqttManager:

    def __init__(self, app, host, port=1883, username=None, password=None):
        self.app = app
        self.host = host
        self.port = port
        self.username = username
        self.password = password

        # MQTT client
        self.client = mqtt.Client()
        
        # Set callbacks
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.topic_handlers = {}

    def connect(self, on_connect=None):
        self.user_on_connect = on_connect

        if self.username or self.password:
            self.client.username_pw_set(self.username, self.password)

        self.client.connect(self.host, self.port)
        self.client.loop_start()

    def subscribe(self, topic, handler, userdata, one_shot=False):
        try:
            self.app.log(f"Subscribing to topic: {topic}")

            self.topic_handlers[topic] = {
                'handler': handler,
                'userdata': userdata,
                'oneShot': one_shot
            }
            self.client.subscribe(topic)
        except Exception as e:
            self.app.log(f"Error subscribing to topic {topic}: {e}")
            self.app.log(traceback.format_exc())

    def subscribe_one_shot(self, topic, handler, userdata):
        try:
            self.subscribe(topic, handler, userdata, True)
        except Exception as e:
            self.app.log(f"Failed to subscribe to topic {topic}: {e}")

    def unsubscribe(self, topic):
        self.app.log(f"Unsubscribing to topic: {topic}")

        self.client.unsubscribe(topic)
        self.topic_handlers.pop(topic, None)

    # Internal callbacks
    def on_connect(self, client, userdata, flags, rc):
        self.app.log(f"MQTT Manager connected with code {rc}")

        # Call user callback if set
        if self.user_on_connect:
            self.user_on_connect(rc)

    def on_message(self, client, userdata, msg):
        self.app.log(f"Received message: {msg.topic} -> {msg.payload}", level="DEBUG")
        topic = msg.topic
        
        to_unsubscribe = []

        # Iterate a copy, in case the handler subscribe/unsubscribe
        for sub_topic, handler_entry in list(self.topic_handlers.items()):
            # Match with wild card handling
            if sub_topic == topic or topic_matches_sub(sub_topic, topic):
                try:
                    payload = msg.payload.decode()
                    handler_entry['handler'](topic, payload, handler_entry['userdata'])
                except Exception as e:
                    self.app.log(f"Error handling message for topic {topic}: {e}")
                    self.app.log(traceback.format_exc())
                finally:
                    if handler_entry.get('oneShot'):
                        to_unsubscribe.append(sub_topic)

        # Remove unsubcribed listeners, usually due to one-shot
        for unsub in to_unsubscribe:
            try:
                self.app.log(f"Unsubscribe {unsub}")
                self.unsubscribe(unsub)
            except Exception as e:
                self.app.log(f"Failed to unsubscribe from {topic}: {e}")
                
