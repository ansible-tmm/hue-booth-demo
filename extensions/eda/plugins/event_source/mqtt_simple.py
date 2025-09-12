"""
Simple MQTT event source plugin for Event-Driven Ansible.

Usage in a rulebook (with --source-dir extensions/eda):

sources:
  - mqtt_simple:
      host: localhost
      port: 1883
      topics:
        - hue/motion/#
      username: "{{ lookup('env', 'MQTT_USER') }}"
      password: "{{ lookup('env', 'MQTT_PASS') }}"
      tls: false

Notes:
- Requires the "aiomqtt" library (added to decision-environment/requirements.txt)
- Emits events of the shape: { "topic": str, "payload": dict or str }
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional
import ssl

try:
    # aiomqtt (https://pypi.org/project/aiomqtt/)
    from aiomqtt import Client as AsyncMqttClient
except Exception as exc:  # pragma: no cover - import error will be shown at runtime
    AsyncMqttClient = None  # type: ignore
    logging.getLogger(__name__).warning("aiomqtt is not installed: %s", exc)


async def main(queue: asyncio.Queue, args: Dict[str, Any]):
    """Entry point for EDA source plugin.

    Args is expected to include:
      - host (str): MQTT broker hostname (default: localhost)
      - port (int): MQTT broker port (default: 1883)
      - topics (list[str]): MQTT topics to subscribe (default: ["#"])
      - username (str, optional)
      - password (str, optional)
      - tls (bool, optional): whether to use TLS (default: False)
    """
    log = logging.getLogger("mqtt_simple")
    if AsyncMqttClient is None:
        raise RuntimeError("aiomqtt is required for mqtt_simple source plugin")

    host: str = str(args.get("host", "localhost"))
    port: int = int(args.get("port", 1883))
    topics: List[str] = list(args.get("topics", ["#"]))
    username: str = args.get("username")
    password: str = args.get("password")
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
    # TLS support can be extended to accept cafile/certfile in args if needed
    if tls:
        # Prefer asyncio-mqtt TLSParameters if available
        tls_set = False
        try:  # pragma: no cover
            from asyncio_mqtt import TLSParameters  # type: ignore

            params: Dict[str, Any] = {}
            if cafile:
                params["ca_certs"] = cafile
            if certfile:
                params["certfile"] = certfile
            if keyfile:
                params["keyfile"] = keyfile
            if insecure:
                # Handled via SSL context verify_mode below when using ssl context
                pass
            client_kwargs["tls_params"] = TLSParameters(**params)
            tls_set = True
        except Exception:
            pass

        if not tls_set:
            # Fallback: build an SSLContext
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
                # Subscribe to requested topics
                for t in topics:
                    await client.subscribe(t)
                    log.info("Subscribed to topic %s", t)

                # Iterate message stream
                async for message in client.messages:
                    try:
                        payload_text = message.payload.decode("utf-8", errors="replace")
                    except Exception:  # pragma: no cover
                        payload_text = str(message.payload)

                    payload_obj: Any
                    try:
                        payload_obj = json.loads(payload_text)
                    except json.JSONDecodeError:
                        payload_obj = payload_text

                    event = {
                        "topic": getattr(message, "topic", None) or getattr(message, "topic", ""),
                        "payload": payload_obj,
                    }
                    await queue.put(event)
        except asyncio.CancelledError:
            log.info("MQTT plugin cancelled; exiting")
            raise
        except Exception as exc:
            log.warning("MQTT connection loop error: %s; reconnecting in %ss", exc, reconnect_delay_seconds)
            await asyncio.sleep(reconnect_delay_seconds)
