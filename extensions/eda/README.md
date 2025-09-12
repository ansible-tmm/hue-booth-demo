# EDA extensions

This directory contains:

- `plugins/event_source/mqtt_simple.py`: A minimal MQTT source plugin for Event-Driven Ansible (aiomqtt-based)
- `rulebooks/rulebook.yml`: Example rulebook to trigger AAP Demo Job on Hue motion

## Using the local plugin

```bash
cd extensions/eda
ansible-rulebook -r rulebooks/rulebook.yml -S . --print-events
# To use the built-in core source instead, keep 'ansible.eda.mqtt' in the rulebook
```

### Plugin arguments

- host (default: localhost)
- port (default: 1883)
- topics (list, default: ["#"]) — e.g., ["hue/motion/#"]
- username (optional)
- password (optional)
- tls (bool, default: false)
- cafile, certfile, keyfile (optional TLS files)
- tls_insecure (bool, default: false)

Emits events like: `{ "topic": "...", "payload": <json or string> }`
