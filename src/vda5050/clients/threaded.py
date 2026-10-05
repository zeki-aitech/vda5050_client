# src/vda5050/clients/threaded.py
"""
AGV and master control clients that need no asyncio.

    agv = ThreadedAGVClient("broker", "Acme", "r1")
    agv.on_order_received(handle_order)     # called on the MQTT thread
    agv.start()                             # returns at once; connects, and
                                            # reconnects, until stop()
    agv.send_state(state)                   # never blocks; False if offline
    agv.stop()                              # OFFLINE, then a clean disconnect

Callbacks run on paho's network thread, one at a time: an application with
its own executor (a ROS node, a GUI) should only queue the message there.
"""

import logging
import threading
from datetime import datetime, timezone
from typing import Callable, List, Optional

from ..core.threaded_client import ThreadedVDA5050Client
from ..models.connection import Connection, ConnectionState
from ..models.factsheet import Factsheet
from ..models.instant_action import InstantActions
from ..models.order import Order
from ..models.state import State
from ..models.visualization import Visualization

logger = logging.getLogger(__name__)


class ThreadedAGVClient(ThreadedVDA5050Client):
    """
    The AGV side: receives ``order`` and ``instantActions``; sends ``state``,
    ``visualization``, ``factsheet`` and ``connection``.

    On every (re)connection it publishes ``ONLINE`` and the last factsheet
    given to send_factsheet(); its last will is ``CONNECTIONBROKEN``; stop()
    publishes ``OFFLINE`` before disconnecting (VDA5050 6.14).
    """

    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs):
        super().__init__(manufacturer, serial_number, broker_url, **kwargs)
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._instant_callbacks: List[Callable[[InstantActions], None]] = []
        self._factsheet: Optional[Factsheet] = None
        self._factsheet_lock = threading.Lock()
        self._subscribe("order", Order, lambda topic, m: self._fan_out(self._order_callbacks, m))
        self._subscribe("instantActions", InstantActions,
                        lambda topic, m: self._fan_out(self._instant_callbacks, m))

    # ── callbacks ─────────────────────────────────────────────

    def on_order_received(self, callback: Callable[[Order], None]) -> None:
        self._order_callbacks.append(callback)

    def on_instant_action(self, callback: Callable[[InstantActions], None]) -> None:
        self._instant_callbacks.append(callback)

    @staticmethod
    def _fan_out(callbacks, message) -> None:
        for cb in list(callbacks):
            try:
                cb(message)
            except Exception:
                logger.exception("VDA5050: %s callback failed", type(message).__name__)

    # ── sending ───────────────────────────────────────────────

    def send_state(self, state: State) -> bool:
        """False, and the state is dropped, if not connected."""
        return self.publish("state", state)

    def send_visualization(self, visualization: Visualization) -> bool:
        return self.publish("visualization", visualization)

    def send_factsheet(self, factsheet: Factsheet) -> bool:
        """
        Keep the factsheet and publish it (retained) now if connected, and
        again on every reconnection. False if it could not be sent now.
        """
        with self._factsheet_lock:
            self._factsheet = factsheet
        return self.publish("factsheet", factsheet)

    def update_connection(self, connection_state: ConnectionState) -> bool:
        """Publish ONLINE or OFFLINE on the connection topic (retained, QoS 1)."""
        return self.publish("connection", self._connection_message(connection_state))

    def _connection_message(self, connection_state: ConnectionState) -> Connection:
        return Connection(
            headerId=0,  # set by publish()
            timestamp=datetime.now(timezone.utc),
            version=self.version,
            manufacturer=self.manufacturer,
            serialNumber=self.serial_number,
            connectionState=connection_state,
        )

    # ── lifecycle hooks ───────────────────────────────────────

    def _before_start(self) -> None:
        topic = self.topic_manager.get_publish_topic("connection")
        with self._publish_lock:
            payload = self._payload(
                "connection", self._connection_message(ConnectionState.CONNECTIONBROKEN), topic
            )
            self._count_header_id(topic)
        self.transport.set_will(topic, payload, qos=1, retain=True)

    def _on_connected(self) -> None:
        self.update_connection(ConnectionState.ONLINE)
        with self._factsheet_lock:
            factsheet = self._factsheet
        if factsheet is not None:
            self.publish("factsheet", factsheet)

    def _before_stop(self) -> None:
        if not self.is_connected():
            return
        topic = self.topic_manager.get_publish_topic("connection")
        with self._publish_lock:
            payload = self._payload(
                "connection", self._connection_message(ConnectionState.OFFLINE), topic
            )
            self._count_header_id(topic)
        # Wait outside the lock: the network thread must stay free to read
        # the acknowledgement (and any message arriving meanwhile).
        if not self.transport.publish_and_wait(topic, payload, qos=1, retain=True, timeout=2.0):
            logger.warning("VDA5050: OFFLINE not acknowledged before disconnecting")


class ThreadedMasterControlClient(ThreadedVDA5050Client):
    """
    The master control side: sends ``order`` and ``instantActions`` to an
    AGV; receives ``state``, ``connection`` and ``factsheet`` of all AGVs,
    and ``visualization`` once on_visualization() is called.
    """

    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs):
        super().__init__(manufacturer, serial_number, broker_url, **kwargs)
        self._state_callbacks: List[Callable[[str, State], None]] = []
        self._connection_callbacks: List[Callable[[str, str], None]] = []
        self._factsheet_callbacks: List[Callable[[str, Factsheet], None]] = []
        self._visualization_callbacks: List[Callable[[str, Visualization], None]] = []
        self._subscribe_all("state", State, self._state_callbacks)
        self._subscribe_all("connection", Connection, self._connection_callbacks,
                            convert=lambda c: c.connectionState.value)
        self._subscribe_all("factsheet", Factsheet, self._factsheet_callbacks)

    def _subscribe_all(self, message_type, model, callbacks, convert=lambda m: m) -> None:
        def deliver(topic: str, message) -> None:
            info = self._sender(topic, message_type)
            if info is None:
                return
            value = convert(message)
            for cb in list(callbacks):
                try:
                    cb(info["serialNumber"], value)
                except Exception:
                    logger.exception("VDA5050: %s callback failed", message_type)
        self._subscribe(message_type, model, deliver, all_manufacturers=True, all_serials=True)

    # ── callbacks: (serial_number, message) ───────────────────

    def on_state_update(self, callback: Callable[[str, State], None]) -> None:
        self._state_callbacks.append(callback)

    def on_connection_change(self, callback: Callable[[str, str], None]) -> None:
        """callback(serial_number, "ONLINE" | "OFFLINE" | "CONNECTIONBROKEN")."""
        self._connection_callbacks.append(callback)

    def on_factsheet(self, callback: Callable[[str, Factsheet], None]) -> None:
        self._factsheet_callbacks.append(callback)

    def on_visualization(self, callback: Callable[[str, Visualization], None]) -> None:
        """The first call subscribes to the visualization topics of all AGVs."""
        first = not self._visualization_callbacks
        self._visualization_callbacks.append(callback)
        if first:
            self._subscribe_all("visualization", Visualization, self._visualization_callbacks)

    # ── sending ───────────────────────────────────────────────

    def send_order(self, target_manufacturer: str, target_serial: str, order: Order) -> bool:
        return self.publish("order", order, target_manufacturer, target_serial)

    def send_instant_action(
        self, target_manufacturer: str, target_serial: str, action: InstantActions
    ) -> bool:
        return self.publish("instantActions", action, target_manufacturer, target_serial)
