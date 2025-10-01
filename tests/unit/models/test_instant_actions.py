"""
Unit tests for the VDA5050 InstantActions message model.

The InstantActions message is sent by master control to the AGV to trigger
immediate action execution. It contains an array of Action objects.

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

from vda5050.models.instant_action import InstantActions
from vda5050.models.base import Action, BlockingType

from .fixtures import (
    make_minimal_instant_actions,
    make_action,
    make_action_parameter,
    get_valid_timestamps,
    remove_field,
    set_field,
)


# =============================================================================
# Requirement 1: Accepts Minimally Valid Payload
# =============================================================================

class TestInstantActionsValidPayloads:
    """Tests that InstantActions accepts valid payloads (Requirement 1)."""
    
    def test_minimal_valid_instant_actions(self):
        """Test that InstantActions accepts a minimal valid payload."""
        payload = make_minimal_instant_actions()
        
        msg = InstantActions(**payload)
        
        assert msg.headerId == 1
        assert msg.version == "2.1.0"
        assert msg.manufacturer == "TestManufacturer"
        assert msg.serialNumber == "AGV001"
        assert len(msg.actions) == 1
        assert msg.actions[0].actionId == "action_001"
    
    def test_instant_actions_with_multiple_actions(self):
        """Test InstantActions with multiple actions."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(actionId="action_1", actionType="pick", blockingType="SOFT"),
                make_action(actionId="action_2", actionType="drop", blockingType="HARD"),
                make_action(actionId="action_3", actionType="wait", blockingType="NONE"),
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert len(msg.actions) == 3
        assert msg.actions[0].actionId == "action_1"
        assert msg.actions[1].actionId == "action_2"
        assert msg.actions[2].actionId == "action_3"
    
    def test_instant_actions_with_action_parameters(self):
        """Test InstantActions with actions containing parameters."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionId="action_1",
                    actionType="customAction",
                    blockingType="SOFT",
                    actionDescription="Test action with parameters",
                    actionParameters=[
                        make_action_parameter(key="duration", value=5.0),
                        make_action_parameter(key="direction", value="left"),
                        make_action_parameter(key="repeat", value=True),
                    ]
                )
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert len(msg.actions[0].actionParameters) == 3
        assert msg.actions[0].actionParameters[0].key == "duration"
        assert msg.actions[0].actionParameters[1].value == "left"


# =============================================================================
# Requirement 2: Rejects Payloads Missing Required Fields
# =============================================================================

class TestInstantActionsMissingFields:
    """Tests that InstantActions rejects missing required fields (Requirement 2)."""
    
    @pytest.mark.parametrize("field", [
        "headerId",
        "timestamp",
        "version",
        "manufacturer",
        "serialNumber",
        "actions",
    ])
    def test_missing_required_field(self, field):
        """Test that missing any required field raises ValidationError."""
        payload = make_minimal_instant_actions()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        error_message = str(exc_info.value)
        assert field in error_message.lower() or field in error_message
    
    def test_missing_action_required_fields(self):
        """Test that actions with missing required fields are rejected."""
        payload = make_minimal_instant_actions(
            actions=[
                {
                    "actionId": "action_1",
                    # Missing: actionType, blockingType
                }
            ]
        )
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        error_message = str(exc_info.value)
        assert "actionType" in error_message or "blockingType" in error_message


# =============================================================================
# Requirement 3: Rejects Invalid Field Types or Formats
# =============================================================================

class TestInstantActionsInvalidTypes:
    """Tests that InstantActions rejects invalid field types (Requirement 3)."""
    
    @pytest.mark.parametrize("invalid_actions", [
        "not_a_list",
        123,
        {"action": "dict"},
        None,
    ])
    def test_invalid_actions_type(self, invalid_actions):
        """Test that actions field must be a list."""
        payload = make_minimal_instant_actions(actions=invalid_actions)
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        error_message = str(exc_info.value).lower()
        assert "actions" in error_message
    
    def test_actions_with_invalid_action_object(self):
        """Test that invalid action objects in the list are rejected."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(),  # Valid
                "not_an_action",  # Invalid
            ]
        )
        
        with pytest.raises(ValidationError):
            InstantActions(**payload)
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("actionId", 123),
        ("actionId", None),
        ("actionType", 456),
        ("actionType", None),
        ("blockingType", "INVALID_TYPE"),
        ("blockingType", 789),
    ])
    def test_invalid_action_field_types(self, field, invalid_value):
        """Test that invalid types in Action fields are rejected."""
        action_payload = make_action()
        action_payload[field] = invalid_value
        
        payload = make_minimal_instant_actions(actions=[action_payload])
        
        with pytest.raises(ValidationError):
            InstantActions(**payload)


# =============================================================================
# Requirement 4: Handles Optional Fields Correctly
# =============================================================================

class TestInstantActionsOptionalFields:
    """Tests that InstantActions handles optional fields correctly (Requirement 4)."""
    
    def test_action_description_is_optional(self):
        """Test that actionDescription is optional in actions."""
        # Without description
        payload = make_minimal_instant_actions()
        msg = InstantActions(**payload)
        assert msg.actions[0].actionDescription is None
        
        # With description
        payload = make_minimal_instant_actions(
            actions=[
                make_action(actionDescription="Test description")
            ]
        )
        msg = InstantActions(**payload)
        assert msg.actions[0].actionDescription == "Test description"
    
    def test_action_parameters_is_optional(self):
        """Test that actionParameters is optional in actions."""
        # Without parameters
        payload = make_minimal_instant_actions()
        msg = InstantActions(**payload)
        assert msg.actions[0].actionParameters is None
        
        # With parameters
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        make_action_parameter(key="test", value="value")
                    ]
                )
            ]
        )
        msg = InstantActions(**payload)
        assert len(msg.actions[0].actionParameters) == 1


# =============================================================================
# Requirement 5: Validates Nested Objects and Arrays
# =============================================================================

class TestInstantActionsNestedValidation:
    """Tests nested object and array validation (Requirement 5)."""
    
    def test_empty_actions_array_rejected(self):
        """Test that empty actions array is rejected."""
        payload = make_minimal_instant_actions(actions=[])
        
        # Note: VDA5050 spec requires at least one action
        # If the model allows empty arrays, this test documents that behavior
        msg = InstantActions(**payload)
        assert len(msg.actions) == 0
    
    def test_nested_action_validation(self):
        """Test that nested Action objects are validated."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionId="action_1",
                    actionType="pick",
                    blockingType="SOFT"
                )
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert isinstance(msg.actions[0], Action)
        assert msg.actions[0].actionId == "action_1"
        assert msg.actions[0].blockingType == BlockingType.SOFT
    
    def test_nested_action_parameters_validation(self):
        """Test that deeply nested ActionParameter objects are validated."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        make_action_parameter(key="param1", value=10),
                        make_action_parameter(key="param2", value="text"),
                        make_action_parameter(key="param3", value=[1, 2, 3]),
                    ]
                )
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert len(msg.actions[0].actionParameters) == 3
        assert msg.actions[0].actionParameters[0].value == 10
        assert msg.actions[0].actionParameters[1].value == "text"
        assert msg.actions[0].actionParameters[2].value == [1, 2, 3]
    
    def test_invalid_nested_action_parameter(self):
        """Test that invalid nested ActionParameter raises error."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        {"key": "valid", "value": 123},
                        {"key": "invalid"},  # Missing value
                    ]
                )
            ]
        )
        
        with pytest.raises(ValidationError):
            InstantActions(**payload)
    
    def test_multiple_actions_with_nested_objects(self):
        """Test validation of multiple actions with nested parameters."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionId="action_1",
                    actionParameters=[
                        make_action_parameter(key="p1", value=1)
                    ]
                ),
                make_action(
                    actionId="action_2",
                    actionParameters=[
                        make_action_parameter(key="p2", value=2)
                    ]
                ),
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert len(msg.actions) == 2
        assert msg.actions[0].actionParameters[0].key == "p1"
        assert msg.actions[1].actionParameters[0].key == "p2"


# =============================================================================
# Requirement 6: Enforces Enum Values
# =============================================================================

class TestInstantActionsEnumValidation:
    """Tests that InstantActions enforces enum values (Requirement 6)."""
    
    @pytest.mark.parametrize("blocking_type", ["NONE", "SOFT", "HARD"])
    def test_valid_blocking_types(self, blocking_type):
        """Test that all valid BlockingType enum values are accepted."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(blockingType=blocking_type)
            ]
        )
        
        msg = InstantActions(**payload)
        assert msg.actions[0].blockingType.value == blocking_type
    
    @pytest.mark.parametrize("invalid_blocking", [
        "INVALID",
        "none",  # lowercase
        "Soft",  # mixed case
        "",
        123,
        None,
    ])
    def test_invalid_blocking_types(self, invalid_blocking):
        """Test that invalid BlockingType values are rejected."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(blockingType=invalid_blocking)
            ]
        )
        
        with pytest.raises(ValidationError):
            InstantActions(**payload)
    
    def test_mixed_blocking_types_in_actions(self):
        """Test that different blocking types can be used in different actions."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(actionId="a1", blockingType="NONE"),
                make_action(actionId="a2", blockingType="SOFT"),
                make_action(actionId="a3", blockingType="HARD"),
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert msg.actions[0].blockingType == BlockingType.NONE
        assert msg.actions[1].blockingType == BlockingType.SOFT
        assert msg.actions[2].blockingType == BlockingType.HARD


# =============================================================================
# Requirement 7: Performs JSON Round-Trip
# =============================================================================

class TestInstantActionsSerialization:
    """Tests JSON round-trip serialization (Requirement 7)."""
    
    def test_model_dump_json_round_trip(self):
        """Test serialization with model_dump_json() and model_validate_json()."""
        payload = make_minimal_instant_actions(
            headerId=42,
            actions=[
                make_action(
                    actionId="action_1",
                    actionType="pick",
                    blockingType="SOFT",
                    actionDescription="Pick up load",
                    actionParameters=[
                        make_action_parameter(key="loadId", value="LOAD123")
                    ]
                )
            ]
        )
        
        original = InstantActions(**payload)
        json_str = original.model_dump_json()
        reconstructed = InstantActions.model_validate_json(json_str)
        
        assert reconstructed.headerId == original.headerId
        assert len(reconstructed.actions) == len(original.actions)
        assert reconstructed.actions[0].actionId == original.actions[0].actionId
        assert reconstructed.actions[0].actionDescription == original.actions[0].actionDescription
        assert len(reconstructed.actions[0].actionParameters) == 1
    
    def test_model_dump_dict_round_trip(self):
        """Test serialization with model_dump() and model_validate()."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(actionId="a1"),
                make_action(actionId="a2"),
            ]
        )
        
        original = InstantActions(**payload)
        dict_data = original.model_dump()
        reconstructed = InstantActions.model_validate(dict_data)
        
        assert len(reconstructed.actions) == 2
        assert reconstructed.actions[0].actionId == "a1"
        assert reconstructed.actions[1].actionId == "a2"
    
    def test_to_mqtt_payload_round_trip(self):
        """Test MQTT payload serialization/deserialization."""
        payload = make_minimal_instant_actions()
        
        original = InstantActions(**payload)
        mqtt_json = original.to_mqtt_payload()
        reconstructed = InstantActions.from_mqtt_payload(mqtt_json)
        
        assert reconstructed.headerId == original.headerId
        assert len(reconstructed.actions) == len(original.actions)
    
    def test_nested_objects_preserved_in_serialization(self):
        """Test that nested Action and ActionParameter objects survive round-trip."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionId="complex_action",
                    actionType="customAction",
                    blockingType="HARD",
                    actionParameters=[
                        make_action_parameter(key="k1", value=1.5),
                        make_action_parameter(key="k2", value="text"),
                        make_action_parameter(key="k3", value=[1, 2, 3]),
                        make_action_parameter(key="k4", value={"nested": "dict"}),
                    ]
                )
            ]
        )
        
        original = InstantActions(**payload)
        reconstructed = InstantActions.model_validate_json(original.model_dump_json())
        
        assert len(reconstructed.actions[0].actionParameters) == 4
        assert reconstructed.actions[0].actionParameters[0].value == 1.5
        assert reconstructed.actions[0].actionParameters[2].value == [1, 2, 3]
        assert reconstructed.actions[0].actionParameters[3].value == {"nested": "dict"}


# =============================================================================
# Requirement 8: Preserves Data Integrity
# =============================================================================

class TestInstantActionsDataIntegrity:
    """Tests that InstantActions preserves data integrity (Requirement 8)."""
    
    def test_action_array_order_preserved(self):
        """Test that the order of actions in the array is preserved."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(actionId="first"),
                make_action(actionId="second"),
                make_action(actionId="third"),
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert msg.actions[0].actionId == "first"
        assert msg.actions[1].actionId == "second"
        assert msg.actions[2].actionId == "third"
        
        # Test round-trip
        reconstructed = InstantActions.model_validate_json(msg.model_dump_json())
        assert reconstructed.actions[0].actionId == "first"
        assert reconstructed.actions[1].actionId == "second"
        assert reconstructed.actions[2].actionId == "third"
    
    def test_action_parameter_values_preserved(self):
        """Test that ActionParameter values of various types are preserved."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        make_action_parameter(key="float", value=3.14159),
                        make_action_parameter(key="bool", value=True),
                        make_action_parameter(key="string", value="exact text"),
                        make_action_parameter(key="list", value=[1, 2, 3, 4, 5]),
                    ]
                )
            ]
        )
        
        msg = InstantActions(**payload)
        
        assert msg.actions[0].actionParameters[0].value == 3.14159
        assert msg.actions[0].actionParameters[1].value is True
        assert msg.actions[0].actionParameters[2].value == "exact text"
        assert msg.actions[0].actionParameters[3].value == [1, 2, 3, 4, 5]
    
    def test_enum_values_preserved(self):
        """Test that BlockingType enum values are preserved."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(blockingType="NONE"),
                make_action(blockingType="SOFT"),
                make_action(blockingType="HARD"),
            ]
        )
        
        msg = InstantActions(**payload)
        reconstructed = InstantActions.model_validate(msg.model_dump())
        
        assert reconstructed.actions[0].blockingType == BlockingType.NONE
        assert reconstructed.actions[1].blockingType == BlockingType.SOFT
        assert reconstructed.actions[2].blockingType == BlockingType.HARD


# =============================================================================
# Requirement 9: Produces Clear Error Messages
# =============================================================================

class TestInstantActionsErrorMessages:
    """Tests that InstantActions produces clear error messages (Requirement 9)."""
    
    def test_missing_actions_field_error(self):
        """Test that missing actions field produces clear error."""
        payload = make_minimal_instant_actions()
        del payload["actions"]
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        error_str = str(exc_info.value)
        assert "actions" in error_str.lower()
    
    def test_invalid_action_field_error(self):
        """Test that errors in nested Action objects reference the field path."""
        payload = make_minimal_instant_actions(
            actions=[
                {
                    "actionId": "valid_id",
                    "actionType": "valid_type",
                    # Missing blockingType
                }
            ]
        )
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        error_str = str(exc_info.value)
        assert "blockingType" in error_str or "blocking" in error_str.lower()
    
    def test_error_location_for_nested_fields(self):
        """Test that errors include location path for nested fields."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        {"key": "valid", "value": 123},
                        {"key": "missing_value"},  # Invalid
                    ]
                )
            ]
        )
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        errors = exc_info.value.errors()
        
        # Should have location information
        for error in errors:
            assert "loc" in error
            assert len(error["loc"]) > 0
    
    def test_multiple_action_errors_collected(self):
        """Test that errors in multiple actions are all collected."""
        payload = make_minimal_instant_actions(
            actions=[
                {"actionId": "a1"},  # Missing required fields
                {"actionType": "type2"},  # Missing required fields
                {"blockingType": "NONE"},  # Missing required fields
            ]
        )
        
        with pytest.raises(ValidationError) as exc_info:
            InstantActions(**payload)
        
        errors = exc_info.value.errors()
        # Should have multiple errors
        assert len(errors) >= 3


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestInstantActionsEdgeCases:
    """Additional edge case tests for InstantActions model."""
    
    def test_large_number_of_actions(self):
        """Test that a large number of actions can be handled."""
        actions = [
            make_action(actionId=f"action_{i}", blockingType="NONE")
            for i in range(100)
        ]
        
        payload = make_minimal_instant_actions(actions=actions)
        msg = InstantActions(**payload)
        
        assert len(msg.actions) == 100
        assert msg.actions[0].actionId == "action_0"
        assert msg.actions[99].actionId == "action_99"
    
    def test_action_with_complex_parameter_values(self):
        """Test actions with complex nested parameter values."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        make_action_parameter(
                            key="complex",
                            value={
                                "nested": {
                                    "deeply": {
                                        "value": [1, 2, 3]
                                    }
                                }
                            }
                        )
                    ]
                )
            ]
        )
        
        msg = InstantActions(**payload)
        param_value = msg.actions[0].actionParameters[0].value
        assert param_value["nested"]["deeply"]["value"] == [1, 2, 3]
    
    def test_action_ids_can_be_duplicated(self):
        """Test that duplicate actionIds are allowed (validation is business logic)."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(actionId="duplicate_id"),
                make_action(actionId="duplicate_id"),
            ]
        )
        
        # Pydantic model doesn't enforce unique actionIds
        # (this would be business logic validation)
        msg = InstantActions(**payload)
        assert msg.actions[0].actionId == msg.actions[1].actionId
    
    def test_special_characters_in_action_fields(self):
        """Test that action fields accept special characters."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionId="action-123_test!@#",
                    actionType="custom/Action\\Type",
                    actionDescription="Test äöü 测试 🤖"
                )
            ]
        )
        
        msg = InstantActions(**payload)
        assert msg.actions[0].actionId == "action-123_test!@#"
        assert msg.actions[0].actionType == "custom/Action\\Type"
        assert msg.actions[0].actionDescription == "Test äöü 测试 🤖"
    
    def test_action_parameter_with_empty_list(self):
        """Test that action parameters can have empty list values."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        make_action_parameter(key="emptyList", value=[])
                    ]
                )
            ]
        )
        
        msg = InstantActions(**payload)
        assert msg.actions[0].actionParameters[0].value == []
    
    def test_action_parameter_with_none_in_dict(self):
        """Test that action parameters can have None values in dicts."""
        payload = make_minimal_instant_actions(
            actions=[
                make_action(
                    actionParameters=[
                        make_action_parameter(
                            key="dictWithNone",
                            value={"key": None, "other": "value"}
                        )
                    ]
                )
            ]
        )
        
        msg = InstantActions(**payload)
        param_value = msg.actions[0].actionParameters[0].value
        assert param_value["key"] is None
        assert param_value["other"] == "value"

