# src/vda5050/clients/agv.py

import logging
from typing import Callable

from ..core.base_client import VDA5050BaseClient
from ..models import InstantActions, Order
from ..models.connection import ConnectionState
from ..models.factsheet import Factsheet
from ..models.state import State
from ..models.visualization import Visualization
from ..utils.exceptions import VDA5050Error
from .threaded import ThreadedAGVClient

logger = logging.getLogger(__name__)


class AGVClient(VDA5050BaseClient):
    """
    AGV client for asyncio: receives orders and instant actions from the
    master, publishes factsheet, state, visualization and connection.

    The work is done by ThreadedAGVClient (``self.client``): ONLINE and the
    factsheet on every (re)connection, CONNECTIONBROKEN as last will, OFFLINE
    on disconnect().
    """

    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs):
        super().__init__(manufacturer, serial_number, broker_url, **kwargs)

    def _create_client(self, **kwargs) -> ThreadedAGVClient:
        return ThreadedAGVClient(**kwargs)

    def on_order_received(self, callback: Callable[[Order], None]):
        """Register a callback invoked, on the loop, when an Order arrives."""
        self.client.on_order_received(lambda order: self._post(callback, order))

    def on_instant_action(self, callback: Callable[[InstantActions], None]):
        """Register a callback invoked, on the loop, when InstantActions arrive."""
        self.client.on_instant_action(lambda actions: self._post(callback, actions))

    async def send_factsheet(self, factsheet: Factsheet) -> bool:
        """
        Publish the factsheet (retained); it is kept and published again on
        every reconnection, also when it could not be sent now.
        """
        try:
            if self.client.send_factsheet(factsheet):
                return True
            logger.error("Factsheet not sent now (not connected); it is sent on connection")
        except VDA5050Error as e:
            logger.error("Failed to send factsheet: %s", e)
        return False

    async def send_state(self, state: State) -> bool:
        """Publish a state; False (and dropped) if not connected."""
        try:
            return await self._publish_message("state", state)
        except VDA5050Error as e:
            logger.error("Failed to send state: %s", e)
            return False

    async def send_visualization(self, visualization: Visualization) -> bool:
        """Publish a visualization message; False (and dropped) if not connected."""
        try:
            return await self._publish_message("visualization", visualization)
        except VDA5050Error as e:
            logger.error("Failed to send visualization: %s", e)
            return False

    async def update_connection(self, connection_state: ConnectionState) -> bool:
        """
        Publish this AGV's connection state (retained, QoS 1). Raises
        VDA5050Error if not connected, as 0.1.x did.
        """
        if not self.is_connected():
            raise VDA5050Error("Not connected to VDA5050 system")
        try:
            return self.client.update_connection(connection_state)
        except VDA5050Error as e:
            logger.error("Failed to update connection state: %s", e)
            return False
