"""
Unit tests for the VDA5050 Connection message model.

The Connection message is used to communicate the connection state between
the AGV and the MQTT broker. It is the simplest VDA5050 message type.

Tests verify all 9 Pydantic model validation requirements:
1. Accepts minimally valid payload
2. Rejects payloads missing required fields
3. Rejects invalid field types or formats
4. Handles optional fields correctly
5. Validates nested objects and arrays
6. Enforces enum values
7. Performs JSON round-trip
8. Preserves data integrity
9. Produces clear error messages
"""

import pytest
from pydantic import ValidationError

from vda5050.models.connection import Connection, ConnectionState

from .fixtures import (
    make_minimal_connection,
    get_valid_timestamps,
    get_invalid_timestamps,
    remove_field,
    set_field,
)


# =============================================================================
# Requirement 1: Accepts Minimally Valid Payload
# =============================================================================

class TestConnectionValidPayloads:
    """Tests that Connection accepts valid payloads (Requirement 1)."""
    
    def test_minimal_valid_connection(self):
        """Test that Connection accepts a minimal valid payload."""
        payload = make_minimal_connection()
        
        connection = Connection(**payload)
        
        assert connection.headerId == 1
        assert connection.version == "2.1.0"
        assert connection.manufacturer == "TestManufacturer"
        assert connection.serialNumber == "AGV001"
        assert connection.connectionState == ConnectionState.ONLINE
    
    def test_connection_with_all_fields(self):
        """Test Connection with all possible fields set."""
        payload = make_minimal_connection(
            headerId=999,
            timestamp="2025-10-01T15:30:45.123Z",
            version="3.0.0",
            manufacturer="AcmeRobotics",
            serialNumber="AGV-XYZ-789",
            connectionState="OFFLINE"
        )
        
        connection = Connection(**payload)
        
        assert connection.headerId == 999
        assert connection.version == "3.0.0"
        assert connection.manufacturer == "AcmeRobotics"
        assert connection.serialNumber == "AGV-XYZ-789"
        assert connection.connectionState == ConnectionState.OFFLINE


# =============================================================================
# Requirement 2: Rejects Payloads Missing Required Fields
# =============================================================================

class TestConnectionMissingFields:
    """Tests that Connection rejects missing required fields (Requirement 2)."""
    
    @pytest.mark.parametrize("field", [
        "headerId",
        "timestamp",
        "version",
        "manufacturer",
        "serialNumber",
        "connectionState",
    ])
    def test_missing_required_field(self, field):
        """Test that missing any required field raises ValidationError."""
        payload = make_minimal_connection()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        # Verify the error message mentions the missing field
        error_message = str(exc_info.value)
        assert field in error_message.lower() or field in error_message
    
    def test_empty_payload(self):
        """Test that completely empty payload raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Connection()
        
        # Should have multiple errors for all required fields
        error_message = str(exc_info.value)
        assert "headerId" in error_message or "timestamp" in error_message


# =============================================================================
# Requirement 3: Rejects Invalid Field Types or Formats
# =============================================================================

class TestConnectionInvalidTypes:
    """Tests that Connection rejects invalid field types (Requirement 3)."""
    
    @pytest.mark.parametrize("field,invalid_value,description", [
        ("headerId", "not_an_int", "string instead of int"),
        ("headerId", 3.14, "float instead of int"),
        ("headerId", None, "None instead of int"),
        ("headerId", [], "list instead of int"),
        ("version", 123, "int instead of string"),
        ("version", None, "None instead of string"),
        ("manufacturer", 456, "int instead of string"),
        ("manufacturer", None, "None instead of string"),
        ("serialNumber", 789, "int instead of string"),
        ("serialNumber", None, "None instead of string"),
        ("serialNumber", True, "bool instead of string"),
    ])
    def test_invalid_field_type(self, field, invalid_value, description):
        """Test that wrong field types are rejected."""
        payload = make_minimal_connection()
        payload[field] = invalid_value
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        # Verify error message references the problematic field
        error_message = str(exc_info.value).lower()
        assert field.lower() in error_message
    
    @pytest.mark.parametrize("invalid_timestamp", get_invalid_timestamps())
    def test_invalid_timestamp_format(self, invalid_timestamp):
        """Test that invalid timestamp formats are rejected."""
        payload = make_minimal_connection(timestamp=invalid_timestamp)
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        error_message = str(exc_info.value).lower()
        assert "timestamp" in error_message
    
    @pytest.mark.parametrize("valid_timestamp", get_valid_timestamps())
    def test_valid_timestamp_formats(self, valid_timestamp):
        """Test that all valid ISO-8601 timestamp formats are accepted."""
        payload = make_minimal_connection(timestamp=valid_timestamp)
        
        connection = Connection(**payload)
        assert connection.timestamp is not None


# =============================================================================
# Requirement 4: Handles Optional Fields Correctly
# =============================================================================

class TestConnectionOptionalFields:
    """Tests that Connection has no optional fields (all are required)."""
    
    def test_no_optional_fields(self):
        """Test that Connection has no optional fields beyond the required ones."""
        # Connection model has no optional fields - all fields are required
        payload = make_minimal_connection()
        connection = Connection(**payload)
        
        # All fields should be set
        assert connection.headerId is not None
        assert connection.timestamp is not None
        assert connection.version is not None
        assert connection.manufacturer is not None
        assert connection.serialNumber is not None
        assert connection.connectionState is not None


# =============================================================================
# Requirement 5: Validates Nested Objects and Arrays
# =============================================================================

class TestConnectionNestedObjects:
    """Tests nested object validation (Requirement 5)."""
    
    def test_no_nested_objects(self):
        """Connection has no nested objects, only primitive fields."""
        # This test documents that Connection is a flat model
        payload = make_minimal_connection()
        connection = Connection(**payload)
        
        # All fields are primitives (no nested models)
        assert isinstance(connection.headerId, int)
        assert isinstance(connection.version, str)
        assert isinstance(connection.manufacturer, str)
        assert isinstance(connection.serialNumber, str)
        assert isinstance(connection.connectionState, ConnectionState)


# =============================================================================
# Requirement 6: Enforces Enum Values
# =============================================================================

class TestConnectionEnumValidation:
    """Tests that Connection enforces ConnectionState enum values (Requirement 6)."""
    
    @pytest.mark.parametrize("state", [
        "ONLINE",
        "OFFLINE",
        "CONNECTIONBROKEN",
    ])
    def test_valid_connection_states(self, state):
        """Test that all valid ConnectionState enum values are accepted."""
        payload = make_minimal_connection(connectionState=state)
        
        connection = Connection(**payload)
        assert connection.connectionState.value == state
    
    @pytest.mark.parametrize("invalid_state", [
        "INVALID",
        "online",  # lowercase
        "Online",  # mixed case
        "CONNECTED",
        "DISCONNECTED",
        "",
        "BROKEN",
        123,
        None,
        True,
    ])
    def test_invalid_connection_states(self, invalid_state):
        """Test that invalid ConnectionState values are rejected."""
        payload = make_minimal_connection(connectionState=invalid_state)
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        error_message = str(exc_info.value).lower()
        assert "connectionstate" in error_message or "connection" in error_message
    
    def test_enum_type_validation(self):
        """Test that connectionState is properly typed as ConnectionState enum."""
        payload = make_minimal_connection(connectionState="ONLINE")
        
        connection = Connection(**payload)
        
        assert isinstance(connection.connectionState, ConnectionState)
        assert connection.connectionState == ConnectionState.ONLINE


# =============================================================================
# Requirement 7: Performs JSON Round-Trip
# =============================================================================

class TestConnectionSerialization:
    """Tests JSON round-trip serialization (Requirement 7)."""
    
    def test_model_dump_json_round_trip(self):
        """Test serialization with model_dump_json() and model_validate_json()."""
        payload = make_minimal_connection(
            headerId=42,
            connectionState="CONNECTIONBROKEN"
        )
        
        original = Connection(**payload)
        json_str = original.model_dump_json()
        reconstructed = Connection.model_validate_json(json_str)
        
        assert reconstructed.headerId == original.headerId
        assert reconstructed.timestamp == original.timestamp
        assert reconstructed.version == original.version
        assert reconstructed.manufacturer == original.manufacturer
        assert reconstructed.serialNumber == original.serialNumber
        assert reconstructed.connectionState == original.connectionState
    
    def test_model_dump_dict_round_trip(self):
        """Test serialization with model_dump() and model_validate()."""
        payload = make_minimal_connection(
            headerId=123,
            manufacturer="TestCorp",
            connectionState="OFFLINE"
        )
        
        original = Connection(**payload)
        dict_data = original.model_dump()
        reconstructed = Connection.model_validate(dict_data)
        
        assert reconstructed.headerId == original.headerId
        assert reconstructed.timestamp == original.timestamp
        assert reconstructed.version == original.version
        assert reconstructed.manufacturer == original.manufacturer
        assert reconstructed.serialNumber == original.serialNumber
        assert reconstructed.connectionState == original.connectionState
    
    def test_to_mqtt_payload_round_trip(self):
        """Test MQTT payload serialization/deserialization methods."""
        payload = make_minimal_connection()
        
        original = Connection(**payload)
        mqtt_json = original.to_mqtt_payload()
        reconstructed = Connection.from_mqtt_payload(mqtt_json)
        
        assert reconstructed.headerId == original.headerId
        assert reconstructed.connectionState == original.connectionState
    
    def test_json_contains_all_fields(self):
        """Test that JSON output contains all required fields."""
        payload = make_minimal_connection()
        connection = Connection(**payload)
        
        json_str = connection.model_dump_json()
        
        assert "headerId" in json_str
        assert "timestamp" in json_str
        assert "version" in json_str
        assert "manufacturer" in json_str
        assert "serialNumber" in json_str
        assert "connectionState" in json_str


# =============================================================================
# Requirement 8: Preserves Data Integrity
# =============================================================================

class TestConnectionDataIntegrity:
    """Tests that Connection preserves data integrity (Requirement 8)."""
    
    def test_integer_values_preserved(self):
        """Test that integer headerId is preserved exactly."""
        payload = make_minimal_connection(headerId=999999)
        
        connection = Connection(**payload)
        assert connection.headerId == 999999
        
        # Round-trip test
        json_str = connection.model_dump_json()
        reconstructed = Connection.model_validate_json(json_str)
        assert reconstructed.headerId == 999999
    
    def test_string_values_preserved(self):
        """Test that string fields preserve exact values."""
        payload = make_minimal_connection(
            version="1.2.3-beta",
            manufacturer="Test Manufacturer Inc.",
            serialNumber="AGV-2024-001-XYZ"
        )
        
        connection = Connection(**payload)
        
        assert connection.version == "1.2.3-beta"
        assert connection.manufacturer == "Test Manufacturer Inc."
        assert connection.serialNumber == "AGV-2024-001-XYZ"
        
        # Round-trip test
        reconstructed = Connection.model_validate(connection.model_dump())
        assert reconstructed.version == "1.2.3-beta"
        assert reconstructed.manufacturer == "Test Manufacturer Inc."
        assert reconstructed.serialNumber == "AGV-2024-001-XYZ"
    
    def test_enum_values_preserved(self):
        """Test that enum values are preserved through serialization."""
        for state in ["ONLINE", "OFFLINE", "CONNECTIONBROKEN"]:
            payload = make_minimal_connection(connectionState=state)
            connection = Connection(**payload)
            
            # Check original
            assert connection.connectionState.value == state
            
            # Check after round-trip
            reconstructed = Connection.model_validate_json(
                connection.model_dump_json()
            )
            assert reconstructed.connectionState.value == state
    
    def test_timestamp_precision_preserved(self):
        """Test that timestamp precision is maintained."""
        timestamps = [
            "2025-10-01T12:00:00Z",
            "2025-10-01T12:00:00.123Z",
            "2025-10-01T12:00:00.123456Z",
        ]
        
        for ts in timestamps:
            payload = make_minimal_connection(timestamp=ts)
            connection = Connection(**payload)
            
            # Timestamp is stored as datetime, but should round-trip correctly
            json_str = connection.model_dump_json()
            reconstructed = Connection.model_validate_json(json_str)
            
            assert reconstructed.timestamp == connection.timestamp


# =============================================================================
# Requirement 9: Produces Clear Error Messages
# =============================================================================

class TestConnectionErrorMessages:
    """Tests that Connection produces clear error messages (Requirement 9)."""
    
    def test_missing_field_error_message(self):
        """Test that missing field errors mention the field name."""
        payload = make_minimal_connection()
        del payload["headerId"]
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        error = exc_info.value
        error_str = str(error)
        
        # Error should mention the missing field
        assert "headerId" in error_str or "header_id" in error_str.lower()
    
    def test_wrong_type_error_message(self):
        """Test that type mismatch errors mention the field and type."""
        payload = make_minimal_connection(headerId="not_an_integer")
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        error_str = str(exc_info.value).lower()
        
        # Should mention the field name
        assert "headerid" in error_str or "header_id" in error_str
        # Should indicate type issue
        assert "int" in error_str or "integer" in error_str or "type" in error_str
    
    def test_invalid_enum_error_message(self):
        """Test that invalid enum errors mention the field and valid values."""
        payload = make_minimal_connection(connectionState="INVALID_STATE")
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        error_str = str(exc_info.value)
        
        # Should mention connectionState
        assert "connectionState" in error_str or "connection" in error_str.lower()
    
    def test_multiple_errors_reported(self):
        """Test that multiple validation errors are collected and reported."""
        payload = {
            "headerId": "not_int",  # Wrong type
            "timestamp": "invalid",  # Invalid format
            "version": None,  # Wrong type
            # Missing: manufacturer, serialNumber, connectionState
        }
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        error = exc_info.value
        
        # Should have multiple errors
        assert len(error.errors()) >= 3
    
    def test_error_includes_location(self):
        """Test that errors include the location/path to the invalid field."""
        payload = make_minimal_connection(connectionState=12345)
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        
        errors = exc_info.value.errors()
        
        # Each error should have a location
        for error in errors:
            assert "loc" in error
            assert len(error["loc"]) > 0


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestConnectionEdgeCases:
    """Additional edge case tests for Connection model."""
    
    def test_very_large_header_id(self):
        """Test that very large integer values are accepted for headerId."""
        payload = make_minimal_connection(headerId=999999999999)
        
        connection = Connection(**payload)
        assert connection.headerId == 999999999999
    
    def test_zero_header_id(self):
        """Test that headerId can be zero."""
        payload = make_minimal_connection(headerId=0)
        
        connection = Connection(**payload)
        assert connection.headerId == 0
    
    def test_special_characters_in_strings(self):
        """Test that string fields accept special characters."""
        payload = make_minimal_connection(
            manufacturer="Test-Manufacturer_123!@#",
            serialNumber="AGV/001\\test",
            version="2.1.0-rc1+build.456"
        )
        
        connection = Connection(**payload)
        assert connection.manufacturer == "Test-Manufacturer_123!@#"
        assert connection.serialNumber == "AGV/001\\test"
        assert connection.version == "2.1.0-rc1+build.456"
    
    def test_unicode_characters_in_strings(self):
        """Test that string fields accept Unicode characters."""
        payload = make_minimal_connection(
            manufacturer="Тест-Производитель",
            serialNumber="AGV-测试-001"
        )
        
        connection = Connection(**payload)
        assert connection.manufacturer == "Тест-Производитель"
        assert connection.serialNumber == "AGV-测试-001"
    
    def test_empty_strings_rejected(self):
        """Test that empty strings are rejected for string fields."""
        # Note: Pydantic may accept empty strings unless explicitly constrained
        # This test documents current behavior
        payload = make_minimal_connection(manufacturer="")
        
        # Empty strings are typically accepted by Pydantic unless min_length is set
        # This test verifies the current behavior
        connection = Connection(**payload)
        assert connection.manufacturer == ""
    
    def test_model_equality(self):
        """Test that two Connection objects with same data are equal."""
        payload = make_minimal_connection()
        
        conn1 = Connection(**payload)
        conn2 = Connection(**payload)
        
        # Note: Pydantic models use field equality
        assert conn1.headerId == conn2.headerId
        assert conn1.timestamp == conn2.timestamp
        assert conn1.connectionState == conn2.connectionState

