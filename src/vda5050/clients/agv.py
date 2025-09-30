# src/vda5050/clients/agv.py

import logging
from typing import Callable, List
from ..core.base_client import VDA5050BaseClient
from ..models import Order, InstantActions
from ..models.factsheet import Factsheet
from ..models.state import State
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
        super().__init__(broker_url, manufacturer, serial_number, **kwargs)
        # Lists of user-registered callbacks
        self._order_callbacks: List[Callable[[Order], None]] = []
        self._instant_callbacks: List[Callable[[InstantActions], None]] = []

    async def _setup_subscriptions(self):
        # Subscribe only to this AGV's order topic
        topic_order = self.topic_manager.get_subscription_topic("order")
        await self.mqtt.subscribe(topic_order, self._handle_order)
        # Subscribe to this AGV's instantActions topic
        topic_inst = self.topic_manager.get_subscription_topic("instantActions")
        await self.mqtt.subscribe(topic_inst, self._handle_instant_action)

    async def _on_vda5050_connect(self):
        # Upon connect, immediately publish factsheet
        logger.debug("AGVClient connected; sending factsheet")
        # Application should have registered factsheet content beforehand
        try:
            await self.send_factsheet(self._factsheet)
        except Exception as e:
            logger.error("Failed to send factsheet on connect: %s", e)

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
                message=factsheet
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

    async def update_connection(self, connection_state: str) -> bool:
        """
        Publish this AGV's connection status.
        """
        if not self._connected:
            raise VDA5050Error("Not connected to VDA5050 system")
            
        try:
            topic = self.topic_manager.get_publish_topic("connection")
            # For connection messages, we can publish the raw string
            success = await self.mqtt.publish(topic, connection_state)
            if not success:
                raise VDA5050Error("Failed to publish connection message")
            logger.debug(f"Published connection state to {topic}")
            return True
        except Exception as e:
            logger.error("Failed to update connection state: %s", e)
            return False
