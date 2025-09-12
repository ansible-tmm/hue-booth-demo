# hue-booth-demo
Using Ansible Automation Platform &amp; Philips Hue

Note: This repo includes a simple Event-Driven Ansible MQTT event source plugin at `plugins/event_source/mqtt_simple.py`, suitable for publishing on Ansible Galaxy (e.g., namespace `ansible_tmm.hue_booth_demo`).

# Setup

```bash
python3 -m venv .hue-booth-demo && source .hue-booth-demo/bin/activate
pip install aiohttp paho-mqtt
```

## Run the application

Use Python 3 and the virtual environment created above.

```bash
# Activate the venv (if not already active)
source .hue-booth-demo/bin/activate

# Ensure dependencies are installed
pip install aiohttp paho-mqtt

# Required Hue key (and optional IP override)
export HUE_KEY=...                # required
export HUE_BRIDGE_IP=192.168.1.71 # optional, defaults to this value

# Optional MQTT settings
export MQTT_HOST=localhost
export MQTT_PORT=1883
```

To run the bridge -> MQTT streamer
```
python3 hue_to_mqtt.py
```

# Reference Documentaiton

How to setup API for Philips Hue: https://developers.meethue.com/develop/get-started-2/

API v2 setup guide: https://developers.meethue.com/develop/hue-api-v2/getting-started/

## Hue Bridge setup

1. Find your Hue Bridge IP (shown in the Hue app or via your router). Replace `192.168.1.71` below.
2. Press the physical link button on the Hue Bridge.
3. Within 30 seconds, run:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"devicetype":"myapp#mydev"}' \
  http://192.168.1.71/api
```

You should see a response containing a username/key:

```json
[ { "success": { "username": "Jk1JzXabc123xyz..." } } ]
```

Export this value as `HUE_KEY` in your shell profile so it is available to `hue_to_mqtt.py`:

```bash
# Example for zsh
echo 'export HUE_KEY=Jk1JzXabc123xyz...' >> ~/.zshrc
# If you use oh-my-zsh, you can also append to ~/.oh-my-zsh/oh-my-zsh.sh
source ~/.zshrc
```

Optionally set MQTT variables too:

```bash
echo 'export MQTT_HOST=localhost' >> ~/.zshrc
echo 'export MQTT_PORT=1883' >> ~/.zshrc
source ~/.zshrc
```

## Environment variables

These are read by `hue_to_mqtt.py`.

| Variable       | Required | Default         | Description |
|----------------|----------|-----------------|-------------|
| `HUE_BRIDGE_IP`| no       | `192.168.1.71`  | Hue Bridge IP address |
| `HUE_KEY`      | yes      | —               | Hue API key (username) |
| `MQTT_HOST`    | no       | `localhost`     | MQTT broker hostname/IP |
| `MQTT_PORT`    | no       | `1883`          | MQTT broker port |
| `MQTT_USER`    | no       | empty           | MQTT username |
| `MQTT_PASS`    | no       | empty           | MQTT password |
| `MQTT_PREFIX`  | no       | `hue`           | Topic prefix for published messages |
| `HUE_SSL_VERIFY` | no    | `0` (off)       | Verify Hue bridge TLS cert (set `1` to enable) |
| `MQTT_TLS_ENABLE` | no   | `0` (off)       | Enable MQTT over TLS (usually port 8883) |
| `MQTT_TLS_INSECURE` | no | `0` (off)       | Skip MQTT TLS cert verification (set `1` to allow self-signed) |
| `MQTT_TLS_CAFILE` | no   | empty           | Path to CA bundle to trust for MQTT TLS |
| `HUE_SSE_IDLE_TIMEOUT` | no | `300`        | Seconds without SSE data before auto-reconnect |

## MQTT via Podman/Docker

Quickly run a local Mosquitto broker using Podman Desktop or Docker.

### Start the broker

```bash
cd mqtt
podman compose up -d   # or: docker compose up -d
```

This exposes ports 1883 (plain) and 8883 (TLS-ready if you add certs). Data and logs persist under `mqtt/data` and `mqtt/log`.

### Optional: enable username/password

```bash
podman exec -it hue-booth-mosquitto sh -lc "mosquitto_passwd -c /mosquitto/config/passwords mosuser"
podman restart hue-booth-mosquitto
```

Then add this line in `mqtt/config/mosquitto.conf` (already present but commented) and restart:

```
password_file /mosquitto/config/passwords
```

### Use with hue_to_mqtt.py

Ensure the broker is running, then set environment variables as needed:

```bash
export HUE_KEY=...   # required
export MQTT_HOST=localhost
export MQTT_PORT=1883
python3 hue_to_mqtt.py
```

### TLS/SSL options

Hue bridge TLS verification is off by default to avoid issues with local/self-signed certs. Enable it if you have proper trust set up:

```bash
export HUE_SSL_VERIFY=1
```

To use MQTT over TLS (e.g., Mosquitto on 8883):

```bash
export MQTT_TLS_ENABLE=1
export MQTT_PORT=8883
# If using self-signed certs, either trust a CA file or allow insecure
# Preferred: provide a CA bundle
export MQTT_TLS_CAFILE=/path/to/ca.crt
# Or, allow insecure (skips verification)
# export MQTT_TLS_INSECURE=1

python hue_to_mqtt.py
python3 hue_to_mqtt.py
```

### Show events in the console

Event summaries are ON by default. To disable, set `EVENT_LOG=0`.

```bash
python3 hue_to_mqtt.py
# Example output:
# light/abcd-1234 (Kitchen): on=True, brightness=45
# motion/efgh-5678 (Hallway): presence=True
# temperature/ijkl-9012 (Porch): temperature=21.3
```

### Stopping the application

Press Ctrl+C to exit. The app handles this gracefully and will shut down the MQTT loop and SSE stream without a traceback.

### Sleep/resume notes (macOS)

When a Mac sleeps or the session is locked for a long time, the Hue SSE connection may stall silently. The app now applies an idle read timeout (`HUE_SSE_IDLE_TIMEOUT`, default 300s). If no SSE data arrives for that duration, it will reconnect automatically. MQTT also auto-reconnects with exponential backoff. If you still notice it stuck after very long sleeps, reduce the timeout (e.g., `HUE_SSE_IDLE_TIMEOUT=120`).