"""
EDA source: mqtt_simple
Emits events as: {"topic": <str>, "payload": <dict|str>}
"""

import asyncio
import json
import logging
import ssl
import datetime
import sys
from typing import Any, Dict, List, Optional, Mapping

# --- PROVE we loaded THIS file (prints every import) ---
print(f"[mqtt_simple] Loaded at {datetime.datetime.now()} from {__file__}", file=sys.stderr, flush=True)

# Logger setup (force DEBUG for this module so you see "Validated event")
log = logging.getLogger("mqtt_simple")
if not log.handlers:
    _h = logging.StreamHandler(sys.stderr)
    _h.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    log.addHandler(_h)
log.setLevel(logging.DEBUG)

try:
    from aiomqtt import Client as AsyncMqttClient
except Exception as exc:
    AsyncMqttClient = None  # type: ignore
    logging.getLogger(__name__).warning("aiomqtt is not installed: %s", exc)

def _jsonable(obj: Any) -> Any:
    """Deep-convert to JSON-safe structures."""
    # paho-mqtt v2 Topic
    if hasattr(obj, "value") and obj.__class__.__name__ == "Topic":
        return str(getattr(obj, "value", obj))

    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (bytes, bytearray)):
        return obj.decode("utf-8", errors="replace")
    if isinstance(obj, Mapping):
        return {str(_jsonable(k)): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(x) for x in obj]

    try:
        json.dumps(obj)
        return obj
    except Exception:
        return str(obj)

async def main(queue: asyncio.Queue, args: Dict[str, Any]):
    if AsyncMqttClient is None:
        raise RuntimeError("aiomqtt is required for mqtt_simple source plugin")

    host: str = str(args.get("host", "localhost"))
    port: int = int(args.get("port", 1883))
    topics: List[str] = list(args.get("topics", ["#"]))
    username: Optional[str] = args.get("username")
    password: Optional[str] = args.get("password")
    tls: bool = bool(args.get("tls", False))
    cafile: Optional[str] = args.get("cafile")
    certfile: Optional[str] = args.get("certfile")
    keyfile: Optional[str] = args.get("keyfile")
    insecure: bool = bool(args.get("tls_insecure", False))

    client_kwargs: Dict[str, Any] = {"hostname": host, "port": port}
    if username:
        client_kwargs["username"] = username
    if password:
        client_kwargs["password"] = password

    # TLS optional
    if tls:
        tls_set = False
        try:
            from asyncio_mqtt import TLSParameters  # type: ignore
            params: Dict[str, Any] = {}
            if cafile:   params["ca_certs"] = cafile
            if certfile: params["certfile"] = certfile
            if keyfile:  params["keyfile"]  = keyfile
            client_kwargs["tls_params"] = TLSParameters(**params)
            tls_set = True
        except Exception:
            pass
        if not tls_set:
            context = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
            if insecure:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            if certfile:
                context.load_cert_chain(certfile=certfile, keyfile=keyfile)
            client_kwargs["tls_context"] = context

    reconnect_delay_seconds = 5

    while True:
        try:
            log.info("MQTT connecting to %s:%s", host, port)
            async with AsyncMqttClient(**client_kwargs) as client:
                for t in topics:
                    await client.subscribe(t)
                    log.info("Subscribed to topic %s", t)

                async for message in client.messages:
                    # Topic -> string (handles paho v2 Topic)
                    raw_topic = getattr(message, "topic", "")
                    topic_str = str(getattr(raw_topic, "value", raw_topic))

                    # Payload -> text or JSON object
                    try:
                        payload_text = message.payload.decode("utf-8", errors="replace")
                    except Exception:
                        payload_text = str(message.payload)
                    try:
                        payload_obj = json.loads(payload_text)
                    except json.JSONDecodeError:
                        payload_obj = payload_text

                    event = {"topic": topic_str, "payload": payload_obj}
                    safe_event = _jsonable(event)

                    # Validate before enqueue; if it fails, coerce to strings
                    try:
                        json.dumps(safe_event)
                    except Exception as exc:
                        log.error("Event not JSON-serializable, coercing. err=%s, event=%r", exc, safe_event)
                        safe_event = {"topic": str(topic_str), "payload": str(payload_obj)}

                    # --- PROVE what we will put on the queue (DEBUG) ---
                    log.debug("Validated event: %s", json.dumps(safe_event))

                    await queue.put(safe_event)

        except asyncio.CancelledError:
            log.info("MQTT plugin cancelled; exiting")
            raise
        except Exception as exc:
            log.warning("MQTT loop error: %s; reconnecting in %ss", exc, reconnect_delay_seconds)
            await asyncio.sleep(reconnect_delay_seconds)
