from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, confloat

from .base import AgvPosition, VDA5050Message, Velocity




class Visualization(VDA5050Message):
    agvPosition: Optional[AgvPosition] = Field(
        None, description='The AGVs position', title='agvPosition'
    )
    velocity: Optional[Velocity] = Field(
        None, description='The AGVs velocity in vehicle coordinates', title='velocity'
    )
