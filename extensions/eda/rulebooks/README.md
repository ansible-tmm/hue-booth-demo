# Event-Driven Ansible (EDA) - Hue Motion → AAP Demo Job

This rulebook listens to MQTT motion events from the Hue bridge (via `hue_to_mqtt.py`) and triggers the AAP "Demo Job Template" when motion is detected.

## Requirements

- Ansible EDA (ansible-rulebook)
- Access to your AAP/Controller with a job template named "Demo Job Template" in the "Default" organization
- MQTT broker on `localhost:1883` receiving topics `hue/motion/#`

## Files

- `rulebook.yml`: subscribes to `hue/motion/#` and fires on motion=true

## Run

```bash
cd eda

# If your broker requires auth, export MQTT_USER/MQTT_PASS env vars accordingly

# Dry run to see matched events:
ansible-rulebook -r rulebook.yml -S . --print-events

# Connect to your Controller (AAP) with credentials and run for real:
ansible-rulebook -r rulebook.yml -S . \
  --controller-url https://your-controller \
  --controller-username your-user \
  --controller-password your-pass \
  --controller-verify-ssl false
```

### Notes

- Condition expects messages like:
  - Topic: `hue/motion/<uuid>`
  - Payload JSON includes `type: "motion"` and `motion.motion: true/false`
- On match, it triggers "Demo Job Template" and passes a few useful vars:
  - `sensor_id`, `id_v1`, `changed_at`
