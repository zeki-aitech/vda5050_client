# src/vda5050/core/mqtt_abstraction.py

import asyncio
import logging
import re
from enum import Enum
from typing import Callable, Dict
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    DISCONNECTED = 0
    CONNECTING   = 1
    CONNECTED    = 2
    RECONNECTING = 3

class MQTTAbstraction:
    """
    Async wrapper around paho-mqtt for VDA5050 messaging.
    Provides connect, disconnect, publish, and subscribe methods
    with automatic reconnection and message routing.
    """

    def __init__(
        self,
        broker_url: str,
        broker_port: int = 1883,
        client_id: str = None,
        username: str = None,
        password: str = None,
    ):
        self.broker_url = broker_url
        self.broker_port = broker_port
        # Generate unique client ID if not provided
        self.client_id = client_id or f"vda5050-{asyncio.get_event_loop().time()}"
        self._state = ConnectionState.DISCONNECTED
        self._connection_event = asyncio.Event()
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._handlers: Dict[str, Callable] = {}
        self._wildcard_handlers: Dict[str, Callable] = {}
        self._running = False

        # Configure underlying paho-mqtt client
        self._client = mqtt.Client(client_id=self.client_id)
        if username and password:
            self._client.username_pw_set(username, password)
        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message    = self._on_message

    async def connect(self, timeout: float = 10.0) -> bool:
        """
        Connect to the MQTT broker asynchronously.
        Returns True on success, False on failure.
        """
        if self._state == ConnectionState.CONNECTED:
            return True
        self._state = ConnectionState.CONNECTING
        loop = asyncio.get_event_loop()
        try:
            # Establish connection in executor to avoid blocking
            await loop.run_in_executor(
                None,
                self._client.connect,
                self.broker_url,
                self.broker_port,
                60
            )
            self._client.loop_start()
            # Wait for on_connect callback
            await asyncio.wait_for(self._connection_event.wait(), timeout)
            self._running = True
            # Start processing incoming messages
            asyncio.create_task(self._message_processor())
            return True
        except Exception as e:
            logger.error("MQTT connect failed: %s", e)
            self._state = ConnectionState.DISCONNECTED
            return False

    async def disconnect(self):
        """
        Disconnect gracefully from the MQTT broker.
        """
        self._running = False
        if self._state == ConnectionState.CONNECTED:
            self._client.loop_stop()
            self._client.disconnect()
        self._state = ConnectionState.DISCONNECTED

    async def publish(self, topic: str, payload: str, qos: int = 1) -> bool:
        """
        Publish a message to the given MQTT topic.
        Returns True if published successfully.
        """
        if self._state != ConnectionState.CONNECTED:
            raise RuntimeError("Not connected to MQTT broker")
        loop = asyncio.get_event_loop()
        info = self._client.publish(topic, payload, qos=qos)
        try:
            # Wait for message acknowledgment
            await loop.run_in_executor(None, info.wait_for_publish, 10)
            return True
        except Exception as e:
            logger.error("Publish failed on topic %s: %s", topic, e)
            return False

    async def subscribe(self, topic: str, handler: Callable, qos: int = 1):
        """
        Subscribe to a topic and register an async handler.
        Supports MQTT wildcards ('+' or '#').
        """
        rc, _ = self._client.subscribe(topic, qos=qos)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Subscribe failed for topic {topic}: {rc}")
        if '+' in topic or '#' in topic:
            self._wildcard_handlers[topic] = handler
        else:
            self._handlers[topic] = handler

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Callback when the MQTT client connects to the broker.
        """
        if rc == mqtt.MQTT_ERR_SUCCESS:
            self._state = ConnectionState.CONNECTED
            # Wake up connect()
            asyncio.create_task(self._connection_event.set())
        else:
            logger.error("MQTT on_connect error code %s", rc)

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """
        Callback when the MQTT client disconnects.
        Triggers automatic reconnection on unexpected disconnect.
        """
        self._state = ConnectionState.DISCONNECTED
        self._connection_event.clear()
        if rc != 0:
            # Unexpected disconnect: start reconnect loop
            asyncio.create_task(self._reconnect())

    def _on_message(self, client, userdata, msg, properties=None):
        """
        Callback for incoming messages.
        Queues messages for async processing.
        """
        payload = msg.payload.decode('utf-8')
        asyncio.create_task(self._message_queue.put((msg.topic, payload)))

    async def _message_processor(self):
        """
        Async loop to process queued messages and dispatch to handlers.
        """
        while self._running:
            try:
                topic, payload = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                await self._route(topic, payload)
            except asyncio.TimeoutError:
                continue

    async def _route(self, topic: str, payload: str):
        """
        Route messages to registered handlers, matching exact topics first,
        then MQTT-style wildcard patterns.
        """
        if topic in self._handlers:
            await self._handlers[topic](topic, payload)
            return
        for pattern, handler in self._wildcard_handlers.items():
            # Convert MQTT wildcard to regex
            regex = '^' + pattern.replace('+', '[^/]+').replace('#', '.*') + '$'
            if re.match(regex, topic):
                await handler(topic, payload)
                return

    async def _reconnect(self):
        """
        Automatic reconnection with exponential backoff.
        """
        delay = 1
        while self._state != ConnectionState.CONNECTED:
            logger.info("Reconnecting to MQTT broker in %s seconds...", delay)
            await asyncio.sleep(delay)
            success = await self.connect()
            if success:
                return
            delay = min(delay * 2, 60)
