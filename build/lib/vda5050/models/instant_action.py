from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .base import Action, VDA5050Message


class InstantActions(VDA5050Message):
    actions: List[Action]
