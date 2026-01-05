import appdaemon.plugins.hass.hassapi as hass
import paho.mqtt.client as mqtt
import json
import inspect
import re
import itertools
import traceback
from string import Formatter
from mqtt_manager import MqttManager
from registry import Registry
from config_parser import ConfigParser
import json

# TODO Prefix victron is set in the HA MQTT addon by me
# TODO Maybe listen directly to the victron MQTT instead?
# TODO Handle number of phases dynamically instead of always exposong L1,L2,L3
class VictronLink(hass.Hass):

    def initialize(self):

        self.topic_handlers = {}
        self.registry = Registry(app=self)
        self.devices = {}

        # TODO Better format to parse the result into mappers automatically
        self.pre_setup_config = [
            {
                'name': "bus_number",
                'topic': "victron/N/{vrm_id}/system/0/VebusInstance",
                'handler': self.handle_registry,
                'store': 'bus_id'
            },
            {
                'name': "number_of_phases",
                'topic': "victron/N/{vrm_id}/system/0/Ac/Consumption/NumberOfPhases",
                'handler': self.handle_phases,
                'store': 'phase_id'
            }
        ]

        parser = ConfigParser(app=self, folder="hardware")
        hardware_configs = parser.load_all()

        # TODO vrm_id from config file
        self.config = {
            'vrm_id': "c0619ab8d038",
            'devices': hardware_configs
        }

        # Used to map tags to actual values
        self.registry.add('vrm_id', self.config['vrm_id'])

        mqtt_cfg = self.args.get("mqtt", {})
        self.mqtt_mgr = MqttManager(
            app=self, 
            host="core-mosquitto", 
            port=1883, 
            username=mqtt_cfg.get("username"),
            password=mqtt_cfg.get("password")
        )
        self.mqtt_mgr.connect(self.on_connect)

    def on_connect(self, rc):
        if rc == 0:
            self.log("Connected successfully")
            self.setup()
        else:
            self.log(f"Failed to connect, return code {rc}")

    def setup(self):
        self.log("Running setup...")
        self.pre_setup()

    def pre_setup(self):
        """
        Run pre-setup, fetching the data needed for most other topic, data
        like the VRM ID.
        """

        try:
            self.log("Running pre-setup. Setting up one-shot subscribers...")
            
            # Create a set, keeping track of all the pre-setup calls
            self.pre_setup_pending = set()
            for config in self.pre_setup_config:
                # Keep track of what's left to fetch
                self.pre_setup_pending.add(config['store'])
                self.mqtt_mgr.subscribe_one_shot(config['topic'].format(vrm_id=self.config['vrm_id']), config['handler'], {'store': config['store']})

        except Exception as e:
            self.log(f"Error during pre-setup: {e}")
            self.log(traceback.format_exc())

    def extract_wildcards(self, sub, topic):
        sub_parts = sub.split("/")
        topic_parts = topic.split("/")

        if len(sub_parts) != len(topic_parts):
            return None

        values = []

        for s, t in zip(sub_parts, topic_parts):
            if s == "#":
                # "#" absorbs the rest of the topic
                values.append("/".join(topic_parts[len(values):]))
                return values
            elif s == "+":
                values.append(t)
            elif s != t:
                return None

        return values

    def post_setup(self):
        try:
            self.log("Running post-setup")
            self.discover_devices()
        except Exception as e:
            self.log(f"Error during post-setup: {e}")
            self.log(traceback.format_exc())

    def discover_devices(self):
        try:
            self.log("Discover devices")
            for device_config in self.config['devices']:
                self.log(f"Discover device {device_config['type']}")
                discovery_topic = device_config.get("discovery")
                if discovery_topic:
                    self.mqtt_mgr.subscribe(self.registry.resolve_placeholders(discovery_topic), self.handle_discovery, device_config)
                else:
                    # Device has no discovery, probably because it can't have multiple instances
                    # Just set instance to 0 and add it directly
                    instance = 0
                    device_type = device_config['type']
                    if self.add_device(device_type, instance, device_config):
                        self.log(f"Added new {device_type} device of instance {instance}")
                    
        except Exception as e:
            self.log(f"Error during discover devices: {e}")
            self.log(traceback.format_exc())

    def handle_discovery(self, topic, payload, userdata):
        device_config = userdata
        device_type = device_config['type']

        # Find instance id from the first wild card
        wilds = self.extract_wildcards(self.registry.resolve_placeholders(device_config['discovery']), topic)

        if wilds:
            instance = wilds[0]
            
            if self.add_device(device_type, instance, device_config):
                self.log(f"Added new {device_type} device of instance {instance}")

    def add_device(self, dev_type, instance, config):
        """
        Receive device discovery message. Add a new device if this was the first
        time it sends the message.

        :param dev_type: the device type
        :param instance: the instance id of the device
        :param config: the attached device configuration
        """

        # Create type bucket if missing
        if dev_type not in self.devices:
            self.devices[dev_type] = {}

        # Add only if new
        if instance not in self.devices[dev_type]:
            device = {
                'id': f"{dev_type}_{instance}",
                'instance': instance,
                'dev_type': dev_type,
                'config': config
            }
            self.devices[dev_type][instance] = device
            # TODO Handle none instance devices (system)
            self.registry.add(config['instance_id'], instance, device['id'])
            
            self.device_setup(device)
            
            return True

        return False

    def device_setup(self, device):
        """
        Run device setup. This will fetch device specific data needed for
        topics and Home Assistant device info.

        :param device: the device information
        """

        self.log(f"Device setup {device['config']['type']}[{device['instance']}]")

        config = device['config']
        setup_steps = config.get('setup', [])
        device['setup_steps'] = len(setup_steps)

        if not setup_steps:
            self.log(f"No setup steps for {config['type']}[{device['instance']}], publishing immediately.")
            self.publish_device(device)
            return

        for step in config['setup']:
            topic = self.registry.resolve_placeholders(self.registry.resolve_placeholders(step['topic']), device['id'])

            self.mqtt_mgr.subscribe_one_shot(
                topic, 
                self.setup_receive, 
                {
                    'store': step['store'],
                    'device': device
                }
            )

    def setup_receive(self, topic, payload, userdata):
        """
        Receive method for the device setup MQTT information. This information
        will be saved into the registry for later usage.

        :param topic: the topic that received the message
        :param payload: the payload of the received message
        :param userdata: the userdata of the call
        """

        store = userdata['store']
        device = userdata['device']

        # Extract the message value
        data = json.loads(payload)
        value = str(data["value"])

        # Store the data in the registry
        self.registry.add(store, value, device['id'])

        device['setup_steps'] -= 1

        # If we have receieved all setup data for the device, publish it
        if device['setup_steps'] == 0:
            self.publish_device(device)

    def publish_device(self, device):
        """
        Publish the device. Will resolve all needed device information and then
        publish it to the MQTT bus where Home Assistant will pick it up.

        :param device: the device information
        """

        self.log(f"Publish device: {device['id']}")

        device_config = device['config']

        self.resolve_device_info(device)

        # Publish all the entities of this device to Home Assistant, it will
        # set up HA to listen to them directly
        for entity_config in device_config['entities']:
            self.publish_entity_discover(entity_config, device)

    # Generic data store for dynamic values
    def handle_registry(self, topic, payload, userdata):
        data = json.loads(payload)
        value = int(data["value"])

        self.registry.add(userdata['store'], value)

        self.remove_pre_setup_pending(userdata['store'])

    # TODO Can we do this generically instead?
    def handle_phases(self, topic, payload, userdata):
        data = json.loads(payload)
        phase_count = int(data["value"])
        
        # Generate phase IDs like L1, L2, L3, ... based on phase_count
        self.registry.add('phase_id', [f"L{i+1}" for i in range(phase_count)])

        self.remove_pre_setup_pending(userdata['store'])

    def remove_pre_setup_pending(self, store):
        self.log(f"Pre setup pending before: {self.pre_setup_pending}")
        self.pre_setup_pending.remove(store)

        if len(self.pre_setup_pending) == 0:
            self.post_setup()

    def resolve_device_info(self, device):
        device['device_info'] = self.registry.resolve_placeholders(
            self.registry.resolve_placeholders(device['config']['device_info'],
            device['id'])
        )

        self.log(f"New device info: {device['device_info']}")

    def publish_entity_discover(self, entity_config, device):
        try:
            # Use the entity's value_template if it exists, otherwise default to "{{ value_json.value }}"
            value_template = entity_config.get('value_template', "{{ value_json.value }}")
            # default to sensor
            component = entity_config.get('component', 'sensor') 

            device_info = device['device_info']

            self.log(f"Publishing device info: {device_info}", level="DEBUG")

            entity_id = self.registry.resolve_placeholders(self.registry.resolve_placeholders(entity_config['entity_id']), device['id'])
            state_topic = self.registry.resolve_placeholders(self.registry.resolve_placeholders(entity_config['topic']), device['id'])
            name = self.registry.resolve_placeholders(self.registry.resolve_placeholders(entity_config['name']), device['id'])

            self.publish_discovery(
                entity_id=entity_id,
                state_topic=state_topic,
                name=name,
                device_class=entity_config.get('device_class'),
                unit_of_measurement=entity_config.get('unit_of_measurement'),
                icon=entity_config.get('icon'),
                device=device_info,
                component=component,
                value_template=value_template
            )
        except Exception as e:
            self.log(f"Error during publish entity discover: {e}")
            self.log(traceback.format_exc())

    def publish_discovery(self, entity_id, state_topic, name, device_class=None,
                        unit_of_measurement=None, icon=None, device=None,
                        component="sensor", value_template=None):
        """
        Publish a Home Assistant MQTT discovery message for any entity.

        :param entity_id: unique identifier for this entity
        :param state_topic: the topic HA should subscribe to for state updates
        :param name: human-readable name
        :param device_class: HA device class (optional)
        :param unit_of_measurement: unit of measurement (optional)
        :param icon: mdi icon (optional)
        :param device: dict with device info (optional)
        :param component: HA component type, default "sensor"
        :param value_template: optional value_template string
        """
        discovery_topic = f"homeassistant/{component}/{entity_id}/config"

        payload = {
            "name": name,
            "state_topic": state_topic,
            "unique_id": entity_id,
        }

        if device_class:
            payload["device_class"] = device_class
        if unit_of_measurement:
            payload["unit_of_measurement"] = unit_of_measurement
        if icon:
            payload["icon"] = icon
        if value_template:
            payload["value_template"] = value_template
        if device:
            payload["device"] = device

        # Convert to JSON string
        payload_json = json.dumps(payload)

        # Publish with retain=True so HA remembers it after restart
        self.mqtt_mgr.client.publish(discovery_topic, payload_json, retain=True)
        self.log(f"Published discovery for {entity_id} -> {discovery_topic}")

    def terminate(self):
        self.log("Shutting down MQTT client")
        try:
            # TODO Expose helpers instead?
            self.mqtt_mgr.client.loop_stop()
            self.mqtt_mgr.client.disconnect()
        except Exception as e:
            self.log(f"Error stopping MQTT client: {e}")
