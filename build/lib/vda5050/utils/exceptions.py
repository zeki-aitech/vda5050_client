# src/vda5050/utils/exceptions.py

class VDA5050Error(Exception):
    """Base exception for all VDA5050 client errors."""
    pass

class ConnectionError(VDA5050Error):
    """Raised for MQTT connection issues."""
    pass

class PublishError(VDA5050Error):
    """Raised when publishing a message fails."""
    pass

class ValidationError(VDA5050Error):
    """Raised when message validation against spec fails."""
    pass

class ProtocolError(VDA5050Error):
    """Raised for VDA5050 protocol compliance violations."""
    pass

class TimeoutError(VDA5050Error):
    """Raised when an operation times out."""
    pass
