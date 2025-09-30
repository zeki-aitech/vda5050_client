from __future__ import annotations

from enum import Enum

from pydantic import Field

from .base import VDA5050Message


class ConnectionState(Enum):
    ONLINE = 'ONLINE'
    OFFLINE = 'OFFLINE'
    CONNECTIONBROKEN = 'CONNECTIONBROKEN'


class Connection(VDA5050Message):
    connectionState: ConnectionState = Field(
        ...,
        description='ONLINE: connection between AGV and broker is active. OFFLINE: connection between AGV and broker has gone offline in a coordinated way. CONNECTIONBROKEN: The connection between AGV and broker has unexpectedly ended.',
    )
