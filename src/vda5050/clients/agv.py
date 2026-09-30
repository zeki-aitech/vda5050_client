# src/vda5050/clients/agv.py

import logging
from datetime import datetime, timezone
from typing import Callable, List, Optional
from ..core.base_client import VDA5050BaseClient
from ..models import Order, InstantActions
from ..models.factsheet import Factsheet
from ..models.state import State
from ..models.connection import Connection, ConnectionState
from ..utils.exceptions import VDA5050Error

logger = logging.getLogger(__name__)

class AGVClient(VDA5050BaseClient):
    """
    AGV client: receives orders and instant actions from the master,
    publishes factsheet, state, and connection updates.
    """

    def __init__(
        self,
        broker_url: str,
        manufacturer: str,
        serial_number: str,
        **kwargs
    ):
        # Initialize base client with identity
        super().__init__(manufacturer, serial_number, broker_url, **kwargs)
        # Lists of user-registered callbacks
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._instant_callbacks: List[Callable[[InstantActions], None]] = []
        # Last factsheet sent, re-published on every (re)connect
        self._factsheet: Optional[Factsheet] = None

        # Register handlers using base class API to ensure validation
        # Subscribe to this AGV's specific order and instantActions topics
        self.register_handler("order", self._handle_order)
        self.register_handler("instantActions", self._handle_instant_action)

    async def _setup_subscriptions(self):
        # Subscriptions are now handled by register_handler calls in __init__
        # This method can be used for any non-subscription setup logic if needed
        pass

    def _connection_message(self, connection_state: ConnectionState) -> Connection:
        return Connection(
            headerId=0,  # Connection messages typically use 0
            timestamp=datetime.now(timezone.utc).isoformat(),
            version=self.version,
            manufacturer=self.manufacturer,
            serialNumber=self.serial_number,
            connectionState=connection_state,
        )

    def _configure_will(self):
        """
        VDA5050 requires the AGV's last-will to be a retained
        CONNECTIONBROKEN on its connection topic, so master control learns
        of a crash or lost link from the broker rather than never.
        """
        payload = self._connection_message(ConnectionState.CONNECTIONBROKEN).to_mqtt_payload()
        if self.validator:
            self.validator.validate_message("connection", payload)
        self.mqtt.set_will(
            self.topic_manager.get_publish_topic("connection"),
            payload,
            qos=1,
            retain=True,
        )

    async def _on_vda5050_connect(self):
        # Upon connect, publish connection state and factsheet
        logger.debug("AGVClient connected; sending connection state and factsheet")
        try:
            # Publish ONLINE connection state
            await self.update_connection(ConnectionState.ONLINE)
            # Publish factsheet if available
            if self._factsheet is not None:
                await self.send_factsheet(self._factsheet)
        except Exception as e:
            logger.error("Failed to send connection state or factsheet on connect: %s", e)

    async def _handle_order(self, topic: str, payload: str):
        # Parse JSON into Order model
        try:
            order = Order.from_mqtt_payload(payload)
        except Exception as e:
            logger.error("Failed to parse Order payload: %s", e)
            return
        # Action: Invoke all registered order callbacks
        for cb in self._order_callbacks:
            try:
                cb(order)
            except Exception as e:
                logger.error("Error in order callback: %s", e)

    async def _handle_instant_action(self, topic: str, payload: str):
        # Parse JSON into InstantAction model
        try:
            action = InstantActions.from_mqtt_payload(payload)
        except Exception as e:
            logger.error("Failed to parse InstantAction payload: %s", e)
            return
        # Action: Invoke all registered instant-action callbacks
        for cb in self._instant_callbacks:
            try:
                cb(action)
            except Exception as e:
                logger.error("Error in instant-action callback: %s", e)

    def on_order_received(self, callback: Callable[[Order], None]):
        """
        Register a callback invoked when an Order message arrives.
        """
        self._order_callbacks.append(callback)

    def on_instant_action(self, callback: Callable[[InstantActions], None]):
        """
        Register a callback invoked when an InstantAction message arrives.
        """
        self._instant_callbacks.append(callback)

    async def send_factsheet(self, factsheet: Factsheet) -> bool:
        """
        Publish this AGV's factsheet message.
        Store the factsheet internally for re-publishing on reconnect.
        """
        self._factsheet = factsheet  # store for reconnect
        try:
            return await self._publish_message(
                message_type="factsheet",
                message=factsheet,
                retain=True
            )
        except VDA5050Error as e:
            logger.error("Failed to send factsheet: %s", e)
            return False

    async def send_state(self, state: State) -> bool:
        """
        Publish this AGV's state update.
        """
        try:
            return await self._publish_message(
                message_type="state",
                message=state
            )
        except VDA5050Error as e:
            logger.error("Failed to send state: %s", e)
            return False

    async def update_connection(self, connection_state: ConnectionState) -> bool:
        """
        Publish this AGV's connection status.
        """
        if not self._connected:
            raise VDA5050Error("Not connected to VDA5050 system")
            
        try:
            # Use the standard message publishing mechanism with retain=True for connection state
            return await self._publish_message(
                message_type="connection",
                message=self._connection_message(connection_state),
                retain=True
            )
        except Exception as e:
            logger.error("Failed to update connection state: %s", e)
            return False

    async def _on_vda5050_disconnect(self):
        """
        Called before disconnection - publish OFFLINE state.
        """
        try:
            await self.update_connection(ConnectionState.OFFLINE)
        except Exception as e:
            logger.error("Failed to publish OFFLINE state on disconnect: %s", e)
