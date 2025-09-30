from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, confloat

from .base import AgvPosition, BaseMessage, Velocity




class Visualization(BaseMessage):
    agvPosition: Optional[AgvPosition] = Field(
        None, description='The AGVs position', title='agvPosition'
    )
    velocity: Optional[Velocity] = Field(
        None, description='The AGVs velocity in vehicle coordinates', title='velocity'
    )
