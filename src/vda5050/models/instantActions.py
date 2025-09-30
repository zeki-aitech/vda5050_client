from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .base import Action, BaseMessage


class InstantActions(BaseMessage):
    actions: List[Action]
