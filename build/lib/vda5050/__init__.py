"""
VDA5050 Python Client Library
===============================

A comprehensive Python client library for implementing VDA5050 AGV communication protocol.

This library provides both AGV and Master Control clients with full MQTT integration,
message validation, and callback-based event handling.
"""

__version__ = "0.1.0"
__author__ = "Nguyen Ha Trung (Zekki)"
__email__ = "trungnh.aitech@gmail.com"

# Expose main client classes for convenient imports
from .clients.agv import AGVClient
from .clients.master_control import MasterControlClient

__all__ = [
    "AGVClient",
    "MasterControlClient",
]
