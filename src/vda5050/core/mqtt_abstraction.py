# src/vda5050/core/mqtt_abstraction.py

# this will:
# Wrap the underlying paho-mqtt client in an async/await API
# Manage connection lifecycle (connect, disconnect, automatic reconnect)
# Buffer incoming messages in an asyncio.Queue for non-blocking processing
# Route messages to registered handlers based on exact and wildcard topics
# Expose simple publish(), subscribe(), connect(), and disconnect() methods

import asyncio
import logging
import re
from enum import Enum
from typing import Callable, Dict
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

class ConnectionState(Enum):
    DISCONNECTED = 0
    CONNECTING = 1
    CONNECTED = 2
    RECONNECTING = 3
    
    
class MQTTAbstraction:
    """
    MQTT abstraction layer for VDA5050 communication.
    """
    
    def __init__(
        self,
        broker_url: str,
        broker_port: int = 1883, 
        client_id: str = None,
        username: str = None, 
        password: str = None
    ):
        """
        Initialize the MQTT abstraction.
        
        Args:
            broker_url: The URL of the MQTT broker.
            broker_port: The port of the MQTT broker.
            client_id: The client ID to use for the MQTT connection.
            username: The username to use for the MQTT connection.
            password: The password to use for the MQTT connection.
        """
        
        # Initialize the MQTT client, events, queues, and handler maps
        self.broker_url = broker_url
        self.broker_port = broker_port
        self.client_id = client_id or f"vda5050-client-{asyncio.get_event_loop().time()}" # generate a unique client id if not provided

        self._state = ConnectionState.DISCONNECTED
        self._connection_event = asyncio.Event()
        self._message_queue: asyncio.Queue = asyncio.Queue()
        self._handlers: Dict[str, Callable] = {} # mqtt topic -> handler function
        self._wildcard_handlers: Dict[str, Callable] = {} # mqtt wildcard topic -> handler function
        self._running = False
        
        # Configure MQTT client and callbacks
        self._client = mqtt.Client(client_id=self.client_id)
        if username and password:
            self._client.username_pw_set(username, password)
            
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        
    async def connect(
        self, 
        timeout: float = 10.0
    ) -> bool:
        """
        Connect to the MQTT broker.
        
        Args:
            timeout: The timeout for the connection attempt.
        """
        # Run connect in executor, then wait for on_connect callback
        if self._state == ConnectionState.CONNECTED:
            return True
        self._state = ConnectionState.CONNECTING
        loop = asyncio.get_event_loop()
        
        try:
            await loop.run_in_executor(
                None,
                self._client.connect,
                self.broker_url,
                self.broker_port,
                60 # keepalive timeout - how often to send keepalive messages
            )
            self._client.loop_start()
            await asyncio.wait_for(self._connection_event.wait(), timeout)
            self._running = True
            asyncio.create_task(self._message_processor())
            return True
        except Exception as e:
            logger.error("MQTT connect failed: %s", e)
            return False
        
    async def disconnect(self):
        """
        Disconnect from the MQTT broker.
        """
        # Gracefully stop processor and disconnect
        self._running = False
        if self._state == ConnectionState.CONNECTED:
            self._client.loop_stop()
            self._client.disconnect()
        self._state = ConnectionState.DISCONNECTED
        
    async def publish(
        self, 
        topic: str, 
        payload: str, 
        qos: int = 1
    ) -> bool:
        """
        Publish a message to the MQTT broker.
        
        Args:
            topic: The topic to publish the message to.
            payload: The payload of the message.
            qos: The quality of service level.
        """
        # Wrap publish in executor for async
        if self._state != ConnectionState.CONNECTED:
            raise RuntimeError("Not connected")
        loop = asyncio.get_event_loop()
        info = self._client.publish(topic, payload, qos=qos)
        try:
            await loop.run_in_executor(None, info.wait_for_publish, 10)
            return True
        except Exception as e:
            logger.error("Publish failed: %s", e)
            return False
    
    async def subscribe(
        self, 
        topic: str, 
        handler: Callable, 
        qos: int = 1
    ):
        """
        Subscribe to a topic and register a handler.
        
        Args:
            topic: The topic to subscribe to.
            handler: The handler function to register.
            qos: The quality of service level.
        """
        # Subscribe and register handler
        rc, _ = self._client.subscribe(topic, qos=qos)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Subscribe failed: {rc}")
        # exact or wildcard
        if '+' in topic or '#' in topic:
            self._wildcard_handlers[topic] = handler
        else:
            self._handlers[topic] = handler
            
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """
        Handle connection event.
        """
        # Signal the connection event
        if rc == mqtt.MQTT_ERR_SUCCESS:
            self._state = ConnectionState.CONNECTED
            asyncio.create_task(self._connection_event.set())
        else:
            logger.error("MQTT on_connect returned error %s", rc)
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """
        Handle unexpected disconnect.
        """
        # Handle unexpected disconnect
        self._state = ConnectionState.DISCONNECTED
        self._connection_event.clear()
        if rc != 0:
            asyncio.create_task(self._reconnect())

    def _on_message(self, client, userdata, msg, properties=None):
        """
        Handle incoming messages.
        """
        # Queue incoming messages for async processing
        payload = msg.payload.decode('utf-8')
        asyncio.create_task(self._message_queue.put((msg.topic, payload)))

    async def _message_processor(self):
        """
        Process the message queue until stopped.
        """
        # Process queue until stopped
        while self._running:
            try:
                topic, payload = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0)
                await self._route(topic, payload)
            except asyncio.TimeoutError:
                continue

    async def _route(self, topic: str, payload: str):
        """
        Route the message to the appropriate handler.
        
        Args:
            topic: The topic of the message.
            payload: The payload of the message.
        """
        # Exact match first, then wildcards
        if topic in self._handlers:
            await self._handlers[topic](topic, payload)
            return
        for pattern, handler in self._wildcard_handlers.items():
            # simple MQTT wildcard match
            regex = '^' + pattern.replace('+', '[^/]+').replace('#', '.*') + '$'
            if re.match(regex, topic):
                await handler(topic, payload)
                return

    async def _reconnect(self):
        """
        Reconnect to the MQTT broker.
        """
        # Simple backoff
        delay = 1
        while self._state != ConnectionState.CONNECTED:
            logger.info("Reconnecting in %s seconds...", delay)
            await asyncio.sleep(delay)
            success = await self.connect()
            if success:
                return
            delay = min(delay * 2, 60)
            