# VictronLink (AppDaemon)

VictronLink is an AppDaemon app for integrating Victron inverter system into 
Home Assistant. It consumes data over MQTT, exposes Home Assistant entities, 
and provides sensors for automations and notifications.

The app is designed to be **cloned directly into AppDaemon’s `apps/` directory**
with minimal setup.

---

## Features

- Victron inverter integration
- MQTT-based data ingestion
- Various sensors configurable by yaml
- No cloud dependency
- Designed for long-term reliability

---

## Requirements

- Home Assistant
- AppDaemon (4.x recommended)
- MQTT broker (e.g. Mosquitto)
- Victron system publishing data (e.g. Venus OS / MQTT)

---

## Installation

Clone the repository **directly into your AppDaemon `apps/` directory**:

```bash
cd /path/to/appdaemon/apps
git clone https://github.com/uglybob79/victronlink.git

## Configuration

VictronLink is configured via AppDaemon configuration (usually `apps.yaml`).

---

### Minimal configuration example

Add the following to your **`apps.yaml`**:

```yaml
victronlink:
  module: victronlink
  class: VictronLink

  # MQTT connection
  mqtt_host: core-mosquitto
  mqtt_port: 1883
  mqtt_username: mqtt
  mqtt_password: !secret mqtt_password

  # Victron device identifier
  device_id: abcd1234bcde
