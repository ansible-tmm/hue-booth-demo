# Packaged MQTT source plugin for Event-Driven Ansible

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import ssl

try:
    from aiomqtt import Client as AsyncMqttClient  # type: ignore
except Exception as exc:  # pragma: no cover
    AsyncMqttClient = None  # type: ignore
    logging.getLogger(__name__).warning("aiomqtt is not installed: %s", exc)


async def main(queue: asyncio.Queue, args: Dict[str, Any]):
    log = logging.getLogger("mqtt_simple")
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

    if tls:
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
                    try:
                        payload_text = message.payload.decode("utf-8", errors="replace")
                    except Exception:
                        payload_text = str(message.payload)
                    try:
                        payload_obj: Any = json.loads(payload_text)
                    except json.JSONDecodeError:
                        payload_obj = payload_text
                    event = {"topic": getattr(message, "topic", ""), "payload": payload_obj}
                    await queue.put(event)
        except asyncio.CancelledError:
            log.info("MQTT plugin cancelled; exiting")
            raise
        except Exception as exc:
            log.warning("MQTT connection loop error: %s; reconnecting in %ss", exc, reconnect_delay_seconds)
            await asyncio.sleep(reconnect_delay_seconds)
