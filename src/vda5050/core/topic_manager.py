# src/vda5050/core/topic_manager.py

class TopicManager:
    """
    Manages construction and parsing of MQTT topics for VDA5050 v2.x.
    """

    # Supported VDA5050 message types
    MESSAGE_TYPES = [
        "order",
        "state",
        "connection",
        "factsheet",
        "instantActions",
        "visualization"
    ]

    def __init__(
        self,
        interface_name: str,
        version: str,
        manufacturer: str,
        serial_number: str
    ):
        # Extract the major version (e.g., “2” from “2.1.0”)
        self.interface = interface_name  # e.g., “uagv”
        self.major_version = version.split(".")[0]  # “2”
        self.manufacturer = manufacturer  # AGV vendor
        self.serial_number = serial_number  # AGV identifier

    def _base_topic(self) -> str:
        # Base prefix for this client’s own messages
        return f"{self.interface}/v{self.major_version}/{self.manufacturer}/{self.serial_number}"

    def get_publish_topic(self, message_type: str) -> str:
        """
        Return the MQTT topic for publishing a VDA5050 message from THIS client.
        e.g., "uagv/v2/RobotCorp/robot001/state"
        """
        if message_type not in self.MESSAGE_TYPES:
            raise ValueError(f"Invalid message type: {message_type}")
        # Append messageType to base topic
        return f"{self._base_topic()}/{message_type}"

    def get_target_topic(
        self,
        message_type: str,
        target_manufacturer: str,
        target_serial: str
    ) -> str:
        """
        Return the MQTT topic for sending a message to a specific AGV.
        e.g., "uagv/v2/VendorX/robot123/order"
        """
        if message_type not in self.MESSAGE_TYPES:
            raise ValueError(f"Invalid message type: {message_type}")
        # Build topic for target AGV
        return f"{self.interface}/v{self.major_version}/{target_manufacturer}/{target_serial}/{message_type}"

    def get_subscription_topic(
        self,
        message_type: str,
        all_manufacturers: bool = False,
        all_serials: bool = False
    ) -> str:
        """
        Return the MQTT topic for subscribing to messages.
        Use '+' wildcards for multiple manufacturers or serials.
        """
        if message_type not in self.MESSAGE_TYPES:
            raise ValueError(f"Invalid message type: {message_type}")
        # Use '+' if wildcard requested
        man = "+" if all_manufacturers else self.manufacturer
        serial = "+" if all_serials else self.serial_number
        # Construct subscription topic
        return f"{self.interface}/v{self.major_version}/{man}/{serial}/{message_type}"

    def parse_topic(self, topic: str) -> dict:
        """
        Parse an incoming VDA5050 topic into its components.
        Returns a dict with interface, version, manufacturer, serialNumber, messageType.
        """
        parts = topic.split("/")
        # Must have exactly five segments
        if len(parts) != 5:
            raise ValueError(f"Invalid VDA5050 topic format: {topic}")
        interface, version_tag, man, serial, msg_type = parts

        # Validate interface and version tag
        if interface != self.interface:
            raise ValueError(f"Unexpected interface: {interface}")
        if not version_tag.startswith("v") or not version_tag[1:].isdigit():
            raise ValueError(f"Invalid version tag: {version_tag}")

        version = version_tag[1:]
        if msg_type not in self.MESSAGE_TYPES:
            raise ValueError(f"Unknown message type: {msg_type}")

        # Return structured info
        return {
            "interface": interface,
            "version": version,
            "manufacturer": man,
            "serialNumber": serial,
            "messageType": msg_type
        }
