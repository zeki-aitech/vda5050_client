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
        
        
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        # Signal the connection event
        if rc == mqtt.MQTT_ERR_SUCCESS:
            self._state = ConnectionState.CONNECTED
            asyncio.create_task(self._connection_event.set())
        else:
            logger.error("MQTT on_connect returned error %s", rc)
    
    def _on_disconnect(self, client, userdata, rc, properties=None):
        # Handle unexpected disconnect
        self._state = ConnectionState.DISCONNECTED
        self._connection_event.clear()
        if rc != 0:
            asyncio.create_task(self._reconnect())

    def _on_message(self, client, userdata, msg, properties=None):
        # Queue incoming messages for async processing
        payload = msg.payload.decode('utf-8')
        asyncio.create_task(self._message_queue.put((msg.topic, payload)))
            