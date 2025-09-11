import os, json, asyncio, aiohttp, ssl
import paho.mqtt.client as mqtt

HUE_IP       = os.getenv("HUE_BRIDGE_IP", "192.168.1.71")
HUE_KEY      = os.environ["HUE_KEY"]  # required
MQTT_HOST    = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT    = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER    = os.getenv("MQTT_USER", "")
MQTT_PASS    = os.getenv("MQTT_PASS", "")
MQTT_PREFIX  = os.getenv("MQTT_PREFIX", "hue")
HUE_SSL_VERIFY = os.getenv("HUE_SSL_VERIFY", "0") in ("1", "true", "TRUE", "True", "yes")
MQTT_TLS_ENABLE = os.getenv("MQTT_TLS_ENABLE", "0") in ("1", "true", "TRUE", "True", "yes")
MQTT_TLS_INSECURE = os.getenv("MQTT_TLS_INSECURE", "0") in ("1", "true", "TRUE", "True", "yes")
MQTT_TLS_CAFILE = os.getenv("MQTT_TLS_CAFILE", "")
EVENT_LOG = os.getenv("EVENT_LOG", "1") in ("1", "true", "TRUE", "True", "yes")
HUE_SSE_IDLE_TIMEOUT = int(os.getenv("HUE_SSE_IDLE_TIMEOUT", "300"))  # seconds without data before reconnect

def mqtt_client():
    print(f"Connecting to MQTT {MQTT_HOST}:{MQTT_PORT} TLS={'on' if MQTT_TLS_ENABLE else 'off'}...")
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if MQTT_USER or MQTT_PASS:
        client.username_pw_set(MQTT_USER, MQTT_PASS)
    if MQTT_TLS_ENABLE:
        tls_kwargs = {}
        if MQTT_TLS_CAFILE:
            tls_kwargs["ca_certs"] = MQTT_TLS_CAFILE
        client.tls_set(**tls_kwargs)
        if MQTT_TLS_INSECURE:
            client.tls_insecure_set(True)
    # Set automatic reconnect backoff
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # Basic logging callbacks (API v2 signatures)
    def _on_connect(c, userdata, flags, reason_code, properties=None):
        try:
            rc = int(getattr(reason_code, 'value', reason_code))
        except Exception:
            rc = reason_code
        print(f"MQTT connected rc={rc}")

    def _on_disconnect(c, userdata, disconnect_flags, reason_code, properties=None):
        try:
            rc = int(getattr(reason_code, 'value', reason_code))
        except Exception:
            rc = reason_code
        print(f"MQTT disconnected rc={rc}; will auto-reconnect")

    client.on_connect = _on_connect
    client.on_disconnect = _on_disconnect

    # Use async connect so loop can manage reconnects automatically
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()
    print("MQTT loop started (async connect)")
    return client

def _extract_value(resource, key):
    if key not in resource:
        return None
    value = resource.get(key)
    if isinstance(value, dict) and key in value:
        value = value.get(key)
    return value

def _summarize_resource(resource):
    rtype = resource.get("type", "unknown")
    rid = resource.get("id", "unknown")
    name = None
    metadata = resource.get("metadata") or {}
    if isinstance(metadata, dict):
        name = metadata.get("name")
    fields_of_interest = [
        "on", "dimming", "brightness", "color_temperature", "temperature",
        "motion", "presence", "button", "contact", "tamper", "power_state",
        "battery_state"
    ]
    parts = []
    for key in fields_of_interest:
        val = _extract_value(resource, key)
        if val is None:
            continue
        # Button events sometimes carry nested last_event
        if key == "button" and isinstance(val, dict):
            last_event = val.get("last_event") or val.get("event")
            if last_event is not None:
                parts.append(f"button={last_event}")
                continue
        # Dimming may carry brightness inside dict
        if key == "dimming" and isinstance(val, dict):
            bri = val.get("brightness") or val.get("level")
            if bri is not None:
                parts.append(f"brightness={bri}")
                continue
        # On may be {"on": true}
        if key == "on" and isinstance(val, dict):
            state = val.get("on")
            if state is not None:
                parts.append(f"on={state}")
                continue
        # Temperature could be nested
        if key == "temperature" and isinstance(val, dict):
            t = val.get("temperature") or val.get("value")
            if t is not None:
                parts.append(f"temperature={t}")
                continue
        # Generic scalar
        if isinstance(val, (str, int, float, bool)):
            parts.append(f"{key}={val}")
    base = f"{rtype}/{rid}"
    if name:
        base += f" ({name})"
    if not parts:
        return base + " updated"
    return base + ": " + ", ".join(parts)

async def stream_events():
    url = f"https://{HUE_IP}/eventstream/clip/v2"
    headers = {"hue-application-key": HUE_KEY, "Accept": "text/event-stream"}
    timeout = None
    if HUE_SSE_IDLE_TIMEOUT and HUE_SSE_IDLE_TIMEOUT > 0:
        timeout = aiohttp.ClientTimeout(sock_read=HUE_SSE_IDLE_TIMEOUT)

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                print(f"Connecting to Hue SSE at {url} verify={'on' if HUE_SSL_VERIFY else 'off'}...")
                async with session.get(url, headers=headers, timeout=timeout, ssl=HUE_SSL_VERIFY) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"Hue SSE failed {resp.status}: {text}")
                        await asyncio.sleep(5)
                        continue
                    print("Hue SSE connected; streaming events...")
                    async for line in resp.content:
                        line = line.decode("utf-8").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        try:
                            data = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        yield data
                print("Hue SSE connection closed by server; reconnecting in 5s...")
            except asyncio.CancelledError:
                print("Hue SSE cancelled; exiting...")
                raise
            except (asyncio.TimeoutError, aiohttp.ServerTimeoutError):
                print(f"Hue SSE idle for {HUE_SSE_IDLE_TIMEOUT}s; reconnecting...")
            except Exception as e:
                print(f"Hue SSE error: {e}; reconnecting in 5s...")
            await asyncio.sleep(5)

def publish_bundle(client, bundle):
    # Whole bundle
    client.publish(f"{MQTT_PREFIX}/raw", json.dumps(bundle), qos=0, retain=False)
    # Individual resources
    for item in bundle:
        if not isinstance(item, dict):
            continue
        for res in item.get("data", []):
            rtype = res.get("type", "unknown")
            rid = res.get("id", "unknown")
            topic = f"{MQTT_PREFIX}/{rtype}/{rid}"
            client.publish(topic, json.dumps(res), qos=0, retain=False)
            if EVENT_LOG:
                try:
                    print(_summarize_resource(res))
                except Exception:
                    # Avoid breaking flow on logging errors
                    pass

async def main():
    client = mqtt_client()
    try:
        async for bundle in stream_events():
            publish_bundle(client, bundle)
    finally:
        # Send DISCONNECT while network loop is still running
        try:
            client.disconnect()
        except Exception:
            pass
        # Then stop the network loop
        try:
            client.loop_stop()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Interrupted by user; shutting down...")
    except asyncio.CancelledError:
        print("Cancelled; shutting down...")
