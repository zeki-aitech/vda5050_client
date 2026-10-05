# src/vda5050/core/base_client.py
"""
The asyncio clients: a thin layer over the threaded clients
(clients/threaded.py), which do the MQTT and VDA5050 work. This layer only
moves callbacks from the MQTT thread onto the asyncio loop, in arrival
order, through one queue and one task.
"""

import asyncio
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from ..models.base import VDA5050Message
from ..utils.exceptions import VDA5050Error
from .threaded_client import InvalidMessage, ThreadedVDA5050Client

logger = logging.getLogger(__name__)


class VDA5050BaseClient(ABC):
    """
    Common part of the asyncio AGV and master control clients.

    connect() starts the connection and waits for the first attempt: it
    returns True if connected, False if the broker could not be reached;
    either way the client goes on trying, and reconnects after every loss,
    until disconnect(). Callbacks run on the loop that called connect().

    Extra keyword arguments (client_id, keepalive, reconnect_min_delay,
    reconnect_max_delay) go to the threaded client.
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
        **options: Any,
    ):
        self.client = self._create_client(
            broker_url=broker_url,
            manufacturer=manufacturer,
            serial_number=serial_number,
            broker_port=broker_port,
            interface_name=interface_name,
            version=version,
            username=username,
            password=password,
            validate_messages=validate_messages,
            **options,
        )
        self.manufacturer = manufacturer
        self.serial_number = serial_number
        self.interface_name = interface_name
        self.version = version
        self.validator = self.client.validator
        self.topic_manager = self.client.topic_manager
        # The MQTT transport; its _state is read by applications of 0.1.x.
        self.mqtt = self.client.transport

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._processor: Optional[asyncio.Task] = None

    @abstractmethod
    def _create_client(self, **kwargs) -> ThreadedVDA5050Client:
        """The threaded client this layer wraps."""

    # ── lifecycle ─────────────────────────────────────────────

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Start connecting and wait for the first attempt (at most timeout
        seconds). True if connected. If False, the client keeps trying in
        the background; is_connected() and on_broker_connection() tell when
        it succeeds.
        """
        self._start_processor()
        if self.client.is_connected():
            return True
        logger.info("Connecting VDA5050 client: %s/%s", self.manufacturer, self.serial_number)
        self.client.start()
        loop = asyncio.get_running_loop()
        connected = await loop.run_in_executor(
            None, self.client.transport.wait_first_attempt, timeout
        )
        if not connected:
            logger.warning("VDA5050 client not connected yet; it keeps trying")
        return connected

    async def disconnect(self) -> None:
        """Stop for good: (AGV) OFFLINE, a clean disconnect, no more retries."""
        try:
            await asyncio.get_running_loop().run_in_executor(None, self.client.stop)
        finally:
            await self._stop_processor()

    def is_connected(self) -> bool:
        """True while the MQTT connection is up."""
        return self.client.is_connected()

    # ── callbacks ─────────────────────────────────────────────

    def on_broker_connection(self, callback: Callable[[bool], Any]) -> None:
        """callback(connected) on each connection and loss; see the threaded client."""
        self.client.on_broker_connection(lambda connected: self._post(callback, connected))

    def on_invalid_message(self, callback: Callable[[InvalidMessage], Any]) -> None:
        """callback(InvalidMessage) for each incoming message not delivered."""
        self.client.on_invalid_message(lambda message: self._post(callback, message))

    def register_handler(
        self,
        message_type: str,
        handler: Callable,
        all_manufacturers: bool = False,
        all_serials: bool = False,
    ) -> None:
        """
        await handler(topic, payload) for each message of message_type that
        is JSON and (if validating) passes the schema.
        """
        self.client.register_handler(
            message_type,
            lambda topic, payload: self._post(handler, topic, payload),
            all_manufacturers=all_manufacturers,
            all_serials=all_serials,
        )

    # ── sending ───────────────────────────────────────────────

    async def _publish_message(
        self,
        message_type: str,
        message: VDA5050Message,
        target_manufacturer: Optional[str] = None,
        target_serial: Optional[str] = None,
        retain: bool = False,
    ) -> bool:
        """
        Publish without waiting for an acknowledgement. Raises VDA5050Error
        if not connected or the message is invalid. retain is kept for
        compatibility and ignored: the topic decides (VDA5050 6.14, 6.15).
        """
        if not self.client.publish(message_type, message, target_manufacturer, target_serial):
            raise VDA5050Error(f"Not connected: {message_type} not sent")
        return True

    # ── moving work onto the loop ─────────────────────────────

    def _post(self, fn: Callable, *args: Any) -> None:
        """From the MQTT thread: queue fn(*args) for the processor task."""
        loop, queue = self._loop, self._queue
        if loop is None or queue is None:
            logger.warning("VDA5050: no event loop yet (connect() not awaited); callback dropped")
            return
        try:
            loop.call_soon_threadsafe(queue.put_nowait, (fn, args))
        except RuntimeError:
            logger.warning("VDA5050: event loop closed; callback dropped")

    def _start_processor(self) -> None:
        loop = asyncio.get_running_loop()
        if self._processor is not None and not self._processor.done() and self._loop is loop:
            return
        self._loop = loop
        self._queue = asyncio.Queue()
        self._processor = loop.create_task(self._process())

    async def _stop_processor(self) -> None:
        task, self._processor = self._processor, None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _process(self) -> None:
        """The one task that runs callbacks, in arrival order."""
        while True:
            fn, args = await self._queue.get()
            try:
                result = fn(*args)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("VDA5050: callback %s failed", getattr(fn, "__name__", fn))
