# src/vda5050/core/mqtt_abstraction.py
"""
Kept for applications written against 0.1.x, which import ConnectionState
from here and compare ``client.mqtt._state`` with it. The asyncio
MQTTAbstraction of 0.1.x is gone: the transport is now MQTTTransport
(transport.py), on paho's own thread, and ``client.mqtt`` is one.
"""

from .transport import ConnectionState, MQTTTransport

__all__ = ["ConnectionState", "MQTTTransport"]
