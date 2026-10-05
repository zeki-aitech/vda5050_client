from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, confloat

from .base import AgvPosition, VDA5050Message, Velocity




class Visualization(VDA5050Message):
    # The official schema requires no field at all, the header included;
    # such a message is accepted on receive. The clients fill the header in
    # on send.
    headerId: Optional[int] = Field(
        None,
        description='Header ID of the message. The headerId is defined per topic and incremented by 1 with each sent (but not necessarily received) message.',
    )
    timestamp: Optional[datetime] = Field(
        None,
        description='Timestamp in ISO8601 format (YYYY-MM-DDTHH:mm:ss.ssZ).',
        examples=['1991-03-11T11:40:03.12Z'],
    )
    version: Optional[str] = Field(
        None, description='Version of the protocol [Major].[Minor].[Patch]', examples=['1.3.2']
    )
    manufacturer: Optional[str] = Field(None, description='Manufacturer of the AGV.')
    serialNumber: Optional[str] = Field(None, description='Serial number of the AGV.')
    agvPosition: Optional[AgvPosition] = Field(
        None, description='The AGVs position', title='agvPosition'
    )
    velocity: Optional[Velocity] = Field(
        None, description='The AGVs velocity in vehicle coordinates', title='velocity'
    )
