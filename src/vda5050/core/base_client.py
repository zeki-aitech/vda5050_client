# src/vda5050/core/base_client.py

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Optional, Callable
from .mqtt_abstraction import MQTTAbstraction
from .topic_manager import TopicManager
from ..models.base import VDA5050Message
from ..utils.exceptions import VDA5050Error
from ..validation.validator import MessageValidator

logger = logging.getLogger(__name__)

class VDA5050BaseClient(ABC):
    """
    Abstract base class for all VDA5050 clients.
    Provides common MQTT integration and VDA5050 protocol handling.
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
        validate_messages: bool = True
    ):
        # Store VDA5050 identity for topic construction
        self.manufacturer = manufacturer
        self.serial_number = serial_number
        self.interface_name = interface_name
        self.version = version
        
        # Initialize validation
        self.validator = MessageValidator() if validate_messages else None
        
        # Initialize core components
        self.mqtt = MQTTAbstraction(
            broker_url=broker_url,
            broker_port=broker_port,
            client_id=f"{manufacturer}_{serial_number}",
            username=username,
            password=password
        )
        
        self.topic_manager = TopicManager(
            interface_name=interface_name,
            version=version,
            manufacturer=manufacturer,
            serial_number=serial_number
        )
        
        # Track connection state to prevent double connects
        self._connected = False
        
    async def connect(self) -> bool:
        """
        Connect to VDA5050 system.
        Returns True on success, False on failure.
        """
        # Avoid redundant connections
        if self._connected:
            return True
            
        logger.info(f"Connecting VDA5050 client: {self.manufacturer}/{self.serial_number}")
        
        try:
            # Connect MQTT layer first
            success = await self.mqtt.connect()
            if not success:
                logger.error("MQTT connection failed")
                return False
                
            # Setup VDA5050-specific subscriptions
            await self._setup_subscriptions()
            
            # Setup registered handlers
            await self._setup_registered_handlers()
            
            # Perform client-specific initialization
            await self._on_vda5050_connect()
            
            self._connected = True
            logger.info("VDA5050 client connected successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect VDA5050 client: {e}")
            return False
    
    async def disconnect(self):
        """
        Disconnect from VDA5050 system.
        """
        if not self._connected:
            return
            
        logger.info("Disconnecting VDA5050 client")
        
        try:
            # Client-specific cleanup
            await self._on_vda5050_disconnect()
            
            # Disconnect MQTT
            await self.mqtt.disconnect()
            
            self._connected = False
            logger.info("VDA5050 client disconnected")
            
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
    
    @abstractmethod
    async def _setup_subscriptions(self):
        """
        Setup MQTT subscriptions for this client type.
        Must be implemented by subclasses.
        """
        pass
    
    @abstractmethod
    async def _on_vda5050_connect(self):
        """
        Called after successful VDA5050 connection.
        Must be implemented by subclasses for role-specific initialization.
        """
        pass
    
    async def _on_vda5050_disconnect(self):
        """
        Called before VDA5050 disconnection.
        Can be overridden by subclasses for cleanup.
        """
        pass
    
    async def _publish_message(
        self,
        message_type: str,
        message: VDA5050Message,
        target_manufacturer: Optional[str] = None,
        target_serial: Optional[str] = None
    ) -> bool:
        """
        Publish a VDA5050 message to the appropriate MQTT topic.
        If target_manufacturer and target_serial are provided, builds a
        Master→AGV topic; otherwise publishes from this client.
        """
        if not self._connected:
            raise VDA5050Error("Not connected to VDA5050 system")

        try:
            # Generate payload first (properly serializes datetime to ISO8601 strings)
            payload = message.to_mqtt_payload()
            
            # Validate message before publishing
            if self.validator:
                self.validator.validate_message(message_type, payload)
                logger.debug(f"Message {message_type} passed validation")

            if target_manufacturer and target_serial:
                topic = self.topic_manager.get_target_topic(
                    message_type, target_manufacturer, target_serial
                )
            else:
                topic = self.topic_manager.get_publish_topic(message_type)
            success = await self.mqtt.publish(topic, payload)
            if not success:
                raise VDA5050Error(f"Failed to publish {message_type} message")
            logger.debug(f"Published {message_type} to {topic}")
            return True

        except Exception as e:
            logger.error(f"Error publishing {message_type}: {e}")
            raise VDA5050Error(str(e))
    
    def register_handler(self, message_type: str, handler: Callable, all_manufacturers: bool = False, all_serials: bool = False):
        """
        Register handler for incoming VDA5050 messages.
        The actual subscription will be set up during connection.
        
        Args:
            message_type: VDA5050 message type to handle
            handler: Async function to call when message received
            all_manufacturers: Subscribe to all manufacturers (wildcard)
            all_serials: Subscribe to all serials (wildcard)
        """
        # Store handler registration for later use during connection
        if not hasattr(self, '_registered_handlers'):
            self._registered_handlers = []
        
        self._registered_handlers.append({
            'message_type': message_type,
            'handler': handler,
            'all_manufacturers': all_manufacturers,
            'all_serials': all_serials
        })
    
    async def _setup_registered_handlers(self):
        """Set up MQTT subscriptions for all registered handlers."""
        if not hasattr(self, '_registered_handlers'):
            return
            
        for registration in self._registered_handlers:
            message_type = registration['message_type']
            handler = registration['handler']
            all_manufacturers = registration['all_manufacturers']
            all_serials = registration['all_serials']
            
            # Build topic for this message type
            topic = self.topic_manager.get_subscription_topic(
                message_type, all_manufacturers=all_manufacturers, all_serials=all_serials
            )
            
            # Create wrapper that handles JSON parsing and error catching
            async def message_wrapper(topic: str, payload: str, msg_type=message_type, h=handler):
                try:
                    if self.validator:
                        self.validator.validate_message(msg_type, payload)
                        logger.debug(f"Incoming {msg_type} message passed validation")
                    logger.debug(f"Received {msg_type} message on {topic}")
                    await h(topic, payload)
                except Exception as e:
                    logger.error(f"Error in {msg_type} handler: {e}")
            
            # Subscribe to MQTT topic
            await self.mqtt.subscribe(topic, message_wrapper)
    
    def is_connected(self) -> bool:
        """Check if client is connected to VDA5050 system."""
        return self._connected
