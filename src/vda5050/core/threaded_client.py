# src/vda5050/core/threaded_client.py
"""
The VDA5050 layer over MQTTTransport, with no asyncio. Everything the
standard asks of the transport is here, once:

- QoS by topic (VDA5050 6.2): 1 for ``connection``, 0 for the others;
  ``connection`` and ``factsheet`` retained (6.14, 6.15).
- The header (6.4): ``headerId`` counted per topic by the library (uint32,
  +1 per message sent), the timestamp written in UTC with ``Z``.
- Incoming messages checked (JSON, then the bundled schema, then the model);
  one that fails is handed to the application with the reason, never
  dropped silently.

Callbacks run on paho's network thread, one at a time, in arrival order.
"""

import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple, Type

import paho.mqtt.client as mqtt
import pydantic

from ..models.base import VDA5050Message
from ..utils.exceptions import ValidationError
from ..validation.validator import MessageValidator
from .topic_manager import TopicManager
from .transport import MQTTTransport

logger = logging.getLogger(__name__)

#: MQTT QoS of each topic, VDA5050 6.2 and 6.14.
TOPIC_QOS: Dict[str, int] = {
    "order": 0,
    "instantActions": 0,
    "state": 0,
    "visualization": 0,
    "factsheet": 0,
    "connection": 1,
}

#: Topics whose messages are sent retained, VDA5050 6.14 and 6.15.
RETAINED_TOPICS = frozenset({"connection", "factsheet"})

HEADER_ID_MODULUS = 2 ** 32  # headerId is a uint32


@dataclass(frozen=True)
class InvalidMessage:
    """
    An incoming message that was not delivered.

    kind is ``"json"`` (empty, not UTF-8 or not JSON), ``"schema"`` (fails
    the bundled JSON schema), ``"model"`` (fails the pydantic model) or
    ``"topic"`` (a topic that is not a VDA5050 topic of this interface).
    """
    topic: str
    message_type: str
    kind: str
    reason: str
    payload: bytes


class ThreadedVDA5050Client:
    """
    Common part of the threaded AGV and master control clients.

    Args:
        manufacturer, serial_number: this client's identity; for the AGV
            they are its topic, for a master control they name the client.
        broker_url, broker_port, username, password: the broker.
        interface_name: first topic level (``uagv``).
        version: protocol version put into the header of messages this
            client fills in; its major number goes into the topics.
        validate_messages: check messages against the bundled JSON schemas,
            outgoing and incoming.
        client_id: MQTT client id; ``<manufacturer>_<serial_number>`` if not
            given.
        keepalive, reconnect_min_delay, reconnect_max_delay: see
            MQTTTransport.
    """

    def __init__(
        self,
        manufacturer: str,
        serial_number: str,
        broker_url: str,
        broker_port: int = 1883,
        interface_name: str = "uagv",
        version: str = "2.1.0",
        username: Optional[str] = None,
        password: Optional[str] = None,
        validate_messages: bool = True,
        client_id: Optional[str] = None,
        keepalive: int = 15,
        reconnect_min_delay: int = 1,
        reconnect_max_delay: int = 30,
    ):
        self.manufacturer = manufacturer
        self.serial_number = serial_number
        self.interface_name = interface_name
        self.version = version
        self.validator = MessageValidator() if validate_messages else None
        self.topic_manager = TopicManager(
            interface_name=interface_name,
            version=version,
            manufacturer=manufacturer,
            serial_number=serial_number,
        )
        self.transport = MQTTTransport(
            broker_url=broker_url,
            broker_port=broker_port,
            client_id=client_id or f"{manufacturer}_{serial_number}",
            username=username,
            password=password,
            keepalive=keepalive,
            reconnect_min_delay=reconnect_min_delay,
            reconnect_max_delay=reconnect_max_delay,
        )
        self._publish_lock = threading.RLock()
        self._next_header_id: Dict[str, int] = {}
        self._routes: Dict[str, List[Tuple[Optional[type], Callable[[str, object], None]]]] = {}
        self._routes_lock = threading.Lock()
        self._broker_callbacks: List[Callable[[bool], None]] = []
        self._invalid_callbacks: List[Callable[[InvalidMessage], None]] = []
        self.transport.add_listener(self._on_transport_change)

    # ── lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """
        Start connecting and return at once. The client connects as soon as
        the broker answers and reconnects after every loss, until stop().
        """
        if not self.transport.is_started():
            self._before_start()
            self.transport.start()

    def stop(self) -> None:
        """Leave cleanly: no reconnection, and the broker sends no last will."""
        if self.transport.is_started():
            self._before_stop()
            self.transport.stop()

    def is_connected(self) -> bool:
        """True while the MQTT connection is up."""
        return self.transport.is_connected()

    def wait_connected(self, timeout: Optional[float] = None) -> bool:
        return self.transport.wait_connected(timeout)

    def _before_start(self) -> None:
        """Hook: the AGV arms its last will here."""

    def _before_stop(self) -> None:
        """Hook: the AGV publishes OFFLINE here."""

    def _on_connected(self) -> None:
        """Hook, on the network thread, after the subscriptions are made again."""

    # ── application callbacks ─────────────────────────────────

    def on_broker_connection(self, callback: Callable[[bool], None]) -> None:
        """
        callback(True) after each (re)connection to the broker, once the
        subscriptions are made again and (AGV) ONLINE and the factsheet are
        published; callback(False) when the connection is lost or stopped.
        """
        self._broker_callbacks.append(callback)

    def on_invalid_message(self, callback: Callable[[InvalidMessage], None]) -> None:
        """
        callback(InvalidMessage) for every incoming message that is not
        delivered because it is not JSON or fails the schema or the model.
        Without a callback such messages are logged as warnings.
        """
        self._invalid_callbacks.append(callback)

    def _on_transport_change(self, connected: bool) -> None:
        if connected:
            try:
                self._on_connected()
            except Exception:
                logger.exception("VDA5050: on-connect publishing failed")
        for cb in list(self._broker_callbacks):
            try:
                cb(connected)
            except Exception:
                logger.exception("VDA5050: broker connection callback failed")

    # ── receiving ─────────────────────────────────────────────

    def register_handler(
        self,
        message_type: str,
        handler: Callable[[str, str], None],
        all_manufacturers: bool = False,
        all_serials: bool = False,
    ) -> None:
        """
        handler(topic, payload) for each message of message_type that is
        JSON and (if validating) passes the schema. Wildcards subscribe to
        the topics of all manufacturers or serial numbers.
        """
        self._subscribe(message_type, None, handler, all_manufacturers, all_serials)

    def _subscribe(
        self,
        message_type: str,
        model: Optional[Type[VDA5050Message]],
        deliver: Callable[[str, object], None],
        all_manufacturers: bool = False,
        all_serials: bool = False,
    ) -> None:
        """
        deliver(topic, message) for each valid message of message_type: the
        model instance, or the JSON text when model is None. Routes on the
        same topic share one subscription, so a message is checked, and
        reported if invalid, once.
        """
        topic = self.topic_manager.get_subscription_topic(
            message_type, all_manufacturers=all_manufacturers, all_serials=all_serials
        )
        with self._routes_lock:
            routes = self._routes.setdefault(topic, [])
            first = not routes
            routes.append((model, deliver))
        if first:
            self.transport.subscribe(
                topic, TOPIC_QOS[message_type],
                lambda msg: self._receive(message_type, topic, msg),
            )

    def _receive(self, message_type: str, topic_filter: str, msg: mqtt.MQTTMessage) -> None:
        raw = bytes(msg.payload)

        def invalid(kind: str, reason: str) -> None:
            self._report_invalid(InvalidMessage(msg.topic, message_type, kind, reason, raw))

        if not raw:
            # A zero-length retained message clears the topic on the broker.
            return invalid("json", "empty payload (a retained message was cleared)")
        try:
            text = raw.decode("utf-8")
            data = json.loads(text)
        except (UnicodeDecodeError, ValueError) as e:
            return invalid("json", f"not JSON: {e}")
        if self.validator:
            try:
                self.validator.validate_message(message_type, data)
            except ValidationError as e:
                return invalid("schema", str(e))
        with self._routes_lock:
            routes = list(self._routes.get(topic_filter, ()))
        parsed: Dict[type, object] = {}
        for model, deliver in routes:
            if model is None:
                obj: object = text
            elif model in parsed:
                obj = parsed[model]
            else:
                try:
                    obj = parsed[model] = model.model_validate_json(text)
                except pydantic.ValidationError as e:
                    return invalid("model", str(e))
            try:
                deliver(msg.topic, obj)
            except Exception:
                logger.exception("VDA5050: %s handler failed", message_type)

    def _report_invalid(self, message: InvalidMessage) -> None:
        logger.warning("VDA5050: %s on %s not delivered (%s): %s",
                       message.message_type, message.topic, message.kind, message.reason)
        for cb in list(self._invalid_callbacks):
            try:
                cb(message)
            except Exception:
                logger.exception("VDA5050: invalid-message callback failed")

    def _sender(self, topic: str, message_type: str) -> Optional[Dict[str, str]]:
        """manufacturer and serialNumber from a topic; reports it if malformed."""
        try:
            info = self.topic_manager.parse_topic(topic)
        except ValueError as e:
            self._report_invalid(InvalidMessage(topic, message_type, "topic", str(e), b""))
            return None
        return info

    # ── sending ───────────────────────────────────────────────

    def publish(
        self,
        message_type: str,
        message: VDA5050Message,
        target_manufacturer: Optional[str] = None,
        target_serial: Optional[str] = None,
    ) -> bool:
        """
        Send a message on its topic: this client's own, or that of the
        target AGV. The library sets ``headerId`` (its own counter for the
        topic) and writes the timestamp in UTC; header fields the message
        leaves empty (factsheet, visualization) are filled from this client.

        Returns at once: True if handed to the connection, False if not
        connected (the message is dropped, not kept for later).

        Raises ValidationError if the message fails the schema or its
        timestamp has no time zone.
        """
        if target_manufacturer and target_serial:
            topic = self.topic_manager.get_target_topic(
                message_type, target_manufacturer, target_serial
            )
        else:
            topic = self.topic_manager.get_publish_topic(message_type)
        with self._publish_lock:
            if not self.transport.is_connected():
                logger.debug("VDA5050: not connected; %s dropped", message_type)
                return False
            payload = self._payload(message_type, message, topic)
            ok = self.transport.publish(
                topic, payload, qos=TOPIC_QOS[message_type],
                retain=message_type in RETAINED_TOPICS,
            )
            if ok:
                self._count_header_id(topic)
            return ok

    def _count_header_id(self, topic: str) -> None:
        """The next headerId of topic: +1, and back to 0 after the uint32 maximum."""
        self._next_header_id[topic] = (self._next_header_id.get(topic, 0) + 1) % HEADER_ID_MODULUS

    def _payload(self, message_type: str, message: VDA5050Message, topic: str) -> str:
        """The message as sent on topic: header set, checked, serialised."""
        timestamp = message.timestamp or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            # A naive datetime is local time by Python's convention; taking
            # it as UTC would be wrong by the zone's offset, silently.
            raise ValidationError(
                f"{message_type}: timestamp has no time zone; give an aware "
                "datetime, e.g. datetime.now(timezone.utc)"
            )
        update = {
            "headerId": self._next_header_id.get(topic, 0),
            "timestamp": timestamp.astimezone(timezone.utc),
        }
        for field, value in (("version", self.version),
                             ("manufacturer", self.manufacturer),
                             ("serialNumber", self.serial_number)):
            if getattr(message, field) is None:
                update[field] = value
        payload = message.model_copy(update=update).to_mqtt_payload()
        if self.validator:
            self.validator.validate_message(message_type, payload)
        return payload


__all__ = ["InvalidMessage", "ThreadedVDA5050Client", "TOPIC_QOS", "RETAINED_TOPICS"]
