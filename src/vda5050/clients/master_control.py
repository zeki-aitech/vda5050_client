# src/vda5050/clients/master_control.py

import logging
from typing import Callable

from ..core.base_client import VDA5050BaseClient
from ..models.factsheet import Factsheet
from ..models.instant_action import InstantActions
from ..models.order import Order
from ..models.state import State
from ..models.visualization import Visualization
from ..utils.exceptions import VDA5050Error
from .threaded import ThreadedMasterControlClient

logger = logging.getLogger(__name__)


class MasterControlClient(VDA5050BaseClient):
    """
    Master control client for asyncio: sends orders and instant actions to
    AGVs, and listens for the state, connection and factsheet of all AGVs
    (and visualization, once on_visualization() is called).
    """

    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs):
        super().__init__(manufacturer, serial_number, broker_url, **kwargs)

    def _create_client(self, **kwargs) -> ThreadedMasterControlClient:
        return ThreadedMasterControlClient(**kwargs)

    def on_state_update(self, callback: Callable[[str, State], None]):
        """callback(serial_number, State), on the loop."""
        self.client.on_state_update(lambda serial, state: self._post(callback, serial, state))

    def on_connection_change(self, callback: Callable[[str, str], None]):
        """callback(serial_number, "ONLINE" | "OFFLINE" | "CONNECTIONBROKEN"), on the loop."""
        self.client.on_connection_change(lambda serial, value: self._post(callback, serial, value))

    def on_factsheet(self, callback: Callable[[str, Factsheet], None]):
        """callback(serial_number, Factsheet), on the loop."""
        self.client.on_factsheet(lambda serial, fs: self._post(callback, serial, fs))

    def on_visualization(self, callback: Callable[[str, Visualization], None]):
        """callback(serial_number, Visualization), on the loop; subscribes on first use."""
        self.client.on_visualization(lambda serial, v: self._post(callback, serial, v))

    async def send_order(self, target_manufacturer: str, target_serial: str, order: Order) -> bool:
        try:
            return await self._publish_message(
                "order", order, target_manufacturer=target_manufacturer, target_serial=target_serial
            )
        except VDA5050Error as e:
            logger.error("Failed to send order: %s", e)
            return False

    async def send_instant_action(
        self, target_manufacturer: str, target_serial: str, action: InstantActions
    ) -> bool:
        try:
            return await self._publish_message(
                "instantActions", action,
                target_manufacturer=target_manufacturer, target_serial=target_serial,
            )
        except VDA5050Error as e:
            logger.error("Failed to send instant action: %s", e)
            return False
