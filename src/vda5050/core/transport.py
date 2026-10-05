# src/vda5050/core/transport.py
"""
MQTT transport on paho's own network thread, with no asyncio.

paho's thread connects, retries a first connection that fails, and
reconnects with exponential back-off until stop(). On every (re)connection
the transport makes all its subscriptions again (the session is clean, so the
broker forgets them) and then calls its connection listeners. Publishing
never blocks: a message that cannot be handed to a connected client is
refused and reported by the return value.

Everything the transport calls back (message handlers, listeners) runs on
paho's network thread, one call at a time: keep it short, or hand the work
to another thread.
"""

import logging
import threading
import uuid
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = 0  # not started, or stopped
    CONNECTING   = 1  # started, never connected yet: trying
    CONNECTED    = 2
    RECONNECTING = 3  # was connected, lost the broker: trying again


MessageHandler = Callable[[mqtt.MQTTMessage], None]
ConnectionListener = Callable[[bool], None]


class MQTTTransport:
    """
    One MQTT connection that stays up until stop().

    Args:
        broker_url, broker_port: the broker.
        client_id: MQTT client id; a random one if not given.
        username, password: MQTT login, if the broker wants one.
        keepalive: seconds; VDA5050 6.14 asks for about 15, so a lost link
            is noticed (and the last will sent) within about 1.5 times that.
        reconnect_min_delay, reconnect_max_delay: the back-off between
            attempts, doubling from min to max.

    TLS or other paho options are set on ``transport.paho`` before start().
    """

    def __init__(
        self,
        broker_url: str,
        broker_port: int = 1883,
        client_id: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keepalive: int = 15,
        reconnect_min_delay: int = 1,
        reconnect_max_delay: int = 30,
    ):
        self.broker_url = broker_url
        self.broker_port = broker_port
        self.client_id = client_id or f"vda5050-{uuid.uuid4()}"
        self.keepalive = keepalive
        # Read by applications (and the screen of 0.1.x) to show the link.
        self._state = ConnectionState.DISCONNECTED

        self._lock = threading.RLock()
        self._subscriptions: Dict[str, int] = {}
        self._handlers: Dict[str, List[MessageHandler]] = {}
        self._listeners: List[ConnectionListener] = []
        self._started = False
        self._stopping = False
        self._was_connected = False
        self._failures = 0
        self._connected = threading.Event()
        self._attempted = threading.Event()

        self.paho = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_id)
        if username:
            self.paho.username_pw_set(username, password)
        self.paho.reconnect_delay_set(reconnect_min_delay, reconnect_max_delay)
        self.paho.on_connect = self._on_connect
        self.paho.on_connect_fail = self._on_connect_fail
        self.paho.on_disconnect = self._on_disconnect
        self.paho.on_message = self._on_unrouted_message

    # ── lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """
        Start connecting and return at once. paho's thread keeps trying,
        with back-off, until the broker answers, and reconnects after every
        loss, until stop(). Calling start() again while started does nothing.
        """
        with self._lock:
            if self._started:
                return
            self._started = True
            self._stopping = False
            self._was_connected = False
            self._failures = 0
            self._attempted.clear()
            self._state = ConnectionState.CONNECTING
            self.paho.connect_async(self.broker_url, self.broker_port, self.keepalive)
            self.paho.loop_start()
        logger.info("MQTT: connecting to %s:%s as %s",
                    self.broker_url, self.broker_port, self.client_id)

    def stop(self) -> None:
        """Disconnect cleanly (no last will) and stop the network thread."""
        with self._lock:
            if not self._started:
                return
            self._stopping = True
        self.paho.disconnect()
        self.paho.loop_stop()
        with self._lock:
            self._started = False
            was_connected = self._state == ConnectionState.CONNECTED
            self._state = ConnectionState.DISCONNECTED
            self._connected.clear()
        if was_connected:
            # paho does not call on_disconnect when its thread is stopped
            # before it read the broker's close; tell the listeners here.
            self._notify(False)
        logger.info("MQTT: stopped")

    def is_started(self) -> bool:
        return self._started

    def is_connected(self) -> bool:
        """True while the MQTT connection is up, as paho last reported it."""
        return self._state == ConnectionState.CONNECTED

    def wait_connected(self, timeout: Optional[float] = None) -> bool:
        """Block until connected or the timeout; returns is_connected()."""
        self._connected.wait(timeout)
        return self.is_connected()

    def wait_first_attempt(self, timeout: Optional[float] = None) -> bool:
        """
        Block until the first connection attempt since start() succeeded or
        failed (or the timeout); returns is_connected(). The transport goes
        on trying either way.
        """
        self._attempted.wait(timeout)
        return self.is_connected()

    # ── last will, subscriptions, listeners ───────────────────

    def set_will(self, topic: str, payload: str, qos: int = 1, retain: bool = True) -> None:
        """The message the broker publishes if this client is lost. Before start()."""
        self.paho.will_set(topic, payload, qos=qos, retain=retain)

    def subscribe(self, topic_filter: str, qos: int, handler: MessageHandler) -> None:
        """
        Route messages matching topic_filter (MQTT wildcards allowed) to
        handler, after any handler already registered for that filter. The
        subscription is made now if connected, and again on every
        reconnection.
        """
        with self._lock:
            handlers = self._handlers.setdefault(topic_filter, [])
            first = not handlers
            handlers.append(handler)
            self._subscriptions[topic_filter] = max(qos, self._subscriptions.get(topic_filter, 0))
            qos = self._subscriptions[topic_filter]
            connected = self.is_connected()
        if first:
            self.paho.message_callback_add(topic_filter, self._dispatcher(topic_filter))
        if connected:
            self.paho.subscribe(topic_filter, qos=qos)

    def add_listener(self, listener: ConnectionListener) -> None:
        """
        listener(True) after each (re)connection, once the subscriptions are
        made again; listener(False) when the connection is lost or stopped.
        """
        self._listeners.append(listener)

    # ── publishing ────────────────────────────────────────────

    def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False) -> bool:
        """
        Hand a message to paho and return at once; never waits for an
        acknowledgement. Returns False, and sends nothing later, if not
        connected: nothing is queued for a reconnection.
        """
        return self._publish(topic, payload, qos, retain) is not None

    def publish_and_wait(
        self, topic: str, payload: str, qos: int = 1, retain: bool = False, timeout: float = 2.0
    ) -> bool:
        """Publish and wait until paho has sent it (QoS 1: acknowledged)."""
        info = self._publish(topic, payload, qos, retain)
        if info is None:
            return False
        if threading.current_thread() is getattr(self.paho, "_thread", None):
            return True  # on the network thread: waiting would block it
        try:
            info.wait_for_publish(timeout)
        except (RuntimeError, ValueError) as e:
            logger.warning("MQTT: publish on %s not completed: %s", topic, e)
            return False
        return info.is_published()

    def _publish(self, topic, payload, qos, retain) -> Optional[mqtt.MQTTMessageInfo]:
        if not self.is_connected():
            return None
        info = self.paho.publish(topic, payload, qos=qos, retain=retain)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.debug("MQTT: publish on %s refused by paho: %s",
                         topic, mqtt.error_string(info.rc))
            return None
        return info

    # ── paho callbacks (network thread) ───────────────────────

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            logger.warning("MQTT: broker refused the connection: %s", reason_code)
            self._attempted.set()
            return
        with self._lock:
            self._state = ConnectionState.CONNECTED
            self._failures = 0
            self._was_connected = True
            subscriptions: List[Tuple[str, int]] = list(self._subscriptions.items())
        if subscriptions:
            self.paho.subscribe(subscriptions)
        logger.info("MQTT: connected to %s:%s (%d subscription(s) made)",
                    self.broker_url, self.broker_port, len(subscriptions))
        # Listeners first (the AGV publishes ONLINE and its factsheet there),
        # so wait_connected() returns once all that is done.
        self._notify(True)
        self._connected.set()
        self._attempted.set()

    def _on_connect_fail(self, client, userdata):
        self._failures += 1
        level = logging.WARNING if self._failures == 1 else logging.INFO
        logger.log(level, "MQTT: cannot reach %s:%s (attempt %d); trying again",
                   self.broker_url, self.broker_port, self._failures)
        self._attempted.set()

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        with self._lock:
            was_connected = self._state == ConnectionState.CONNECTED
            self._connected.clear()
            if self._stopping:
                self._state = ConnectionState.DISCONNECTED
            else:
                self._state = (ConnectionState.RECONNECTING if self._was_connected
                               else ConnectionState.CONNECTING)
        if not self._stopping:
            logger.warning("MQTT: connection lost (%s); reconnecting", reason_code)
        if was_connected:
            self._notify(False)

    def _on_unrouted_message(self, client, userdata, msg):
        logger.warning("MQTT: message on %s matches no subscription; ignored", msg.topic)

    # ── helpers ───────────────────────────────────────────────

    def _notify(self, connected: bool) -> None:
        for listener in list(self._listeners):
            try:
                listener(connected)
            except Exception:
                logger.exception("MQTT: connection listener failed")

    def _dispatcher(self, topic_filter: str):
        def dispatch(client, userdata, msg):
            with self._lock:
                handlers = list(self._handlers.get(topic_filter, ()))
            for handler in handlers:
                # An exception escaping a paho callback ends paho's network thread.
                try:
                    handler(msg)
                except Exception:
                    logger.exception("MQTT: handler for %s failed on %s", topic_filter, msg.topic)
        return dispatch
