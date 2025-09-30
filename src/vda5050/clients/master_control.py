# src/vda5050/clients/master_control.py

import logging
from typing import Callable, List
from ..core.base_client import VDA5050BaseClient
from ..models.order import Order
from ..models.instant_action import InstantActions
from ..models.state import State
from ..utils.exceptions import VDA5050Error

logger = logging.getLogger(__name__)

class MasterControlClient(VDA5050BaseClient):
    """
    Master control client: sends orders and instant actions to AGVs,
    and listens for all AGV state and connection updates.
    """

    def __init__(
        self,
        broker_url: str,
        manufacturer: str,
        serial_number: str,
        **kwargs
    ):
        super().__init__(broker_url, manufacturer, serial_number, **kwargs)
        # Callbacks receive (serial: str, state: State)
        self._state_callbacks: List[Callable[[str, State], None]] = []
        self._connection_callbacks: List[Callable[[str, str], None]] = []

    async def _setup_subscriptions(self):
        topic_state = self.topic_manager.get_subscription_topic(
            "state", all_manufacturers=True, all_serials=True
        )
        await self.mqtt.subscribe(topic_state, self._handle_state)

        topic_conn = self.topic_manager.get_subscription_topic(
            "connection", all_manufacturers=True, all_serials=True
        )
        await self.mqtt.subscribe(topic_conn, self._handle_connection)

    async def _on_vda5050_connect(self):
        logger.debug("MasterControlClient connected to VDA5050")

    async def _handle_state(self, topic: str, payload: str):
        info = self.topic_manager.parse_topic(topic)
        if not info:
            logger.error("Invalid state topic: %s", topic)
            return
        try:
            state = State.from_mqtt_payload(payload)
        except Exception as e:
            logger.error("Failed to parse State payload: %s", e)
            return
        serial = info["serialNumber"]
        for cb in self._state_callbacks:
            try:
                cb(serial, state)
            except Exception as e:
                logger.error("Error in state callback: %s", e)

    async def _handle_connection(self, topic: str, payload: str):
        info = self.topic_manager.parse_topic(topic)
        if not info:
            logger.error("Invalid connection topic: %s", topic)
            return
        new_state = payload
        serial = info["serialNumber"]
        for cb in self._connection_callbacks:
            try:
                cb(serial, new_state)
            except Exception as e:
                logger.error("Error in connection callback: %s", e)

    def on_state_update(self, callback: Callable[[str, State], None]):
        """
        Register a callback for AGV state updates.
        Callback receives (serial_number, State).
        """
        self._state_callbacks.append(callback)

    def on_connection_change(self, callback: Callable[[str, str], None]):
        """
        Register a callback for AGV connection state changes.
        Callback receives (serial_number, new_state).
        """
        self._connection_callbacks.append(callback)

    async def send_order(
        self,
        target_manufacturer: str,
        target_serial: str,
        order: Order
    ) -> bool:
        try:
            return await self._publish_message(
                message_type="order",
                message=order,
                target_manufacturer=target_manufacturer,
                target_serial=target_serial
            )
        except VDA5050Error as e:
            logger.error("Failed to send order: %s", e)
            return False

    async def send_instant_action(
        self,
        target_manufacturer: str,
        target_serial: str,
        action: InstantActions
    ) -> bool:
        try:
            return await self._publish_message(
                message_type="instantActions",
                message=action,
                target_manufacturer=target_manufacturer,
                target_serial=target_serial
            )
        except VDA5050Error as e:
            logger.error("Failed to send instant action: %s", e)
            return False
