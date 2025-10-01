"""
Unit tests for the VDA5050 Visualization message model.

The Visualization message provides real-time position and velocity data for
visualization purposes. Most fields are optional except the VDA5050Message header.

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

from vda5050.models.visualization import Visualization
from vda5050.models.base import AgvPosition, Velocity

from .fixtures import (
    make_minimal_visualization,
    make_agv_position,
    make_velocity,
    remove_field,
)


# =============================================================================
# Requirement 1: Accepts Minimally Valid Payload
# =============================================================================

class TestVisualizationValidPayloads:
    """Tests that Visualization accepts valid payloads (Requirement 1)."""
    
    def test_minimal_valid_visualization(self):
        """Test that Visualization accepts minimal valid payload (header only)."""
        payload = make_minimal_visualization()
        
        msg = Visualization(**payload)
        
        assert msg.headerId == 1
        assert msg.version == "2.1.0"
        assert msg.manufacturer == "TestManufacturer"
        assert msg.serialNumber == "AGV001"
        assert msg.agvPosition is None
        assert msg.velocity is None
    
    def test_visualization_with_agv_position(self):
        """Test Visualization with agvPosition set."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position()
        )
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition is not None
        assert msg.agvPosition.x == 10.5
        assert msg.agvPosition.y == 20.3
        assert msg.velocity is None
    
    def test_visualization_with_velocity(self):
        """Test Visualization with velocity set."""
        payload = make_minimal_visualization(
            velocity=make_velocity()
        )
        
        msg = Visualization(**payload)
        
        assert msg.velocity is not None
        assert msg.velocity.vx == 1.5
        assert msg.agvPosition is None
    
    def test_visualization_with_all_fields(self):
        """Test Visualization with all optional fields set."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(
                x=15.5,
                y=25.3,
                theta=1.57,
                mapId="floor2",
                positionInitialized=True,
                localizationScore=0.95,
                deviationRange=0.05
            ),
            velocity=make_velocity(vx=2.0, vy=0.5, omega=0.1)
        )
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition.x == 15.5
        assert msg.agvPosition.localizationScore == 0.95
        assert msg.velocity.vx == 2.0
        assert msg.velocity.vy == 0.5


# =============================================================================
# Requirement 2: Rejects Payloads Missing Required Fields
# =============================================================================

class TestVisualizationMissingFields:
    """Tests that Visualization rejects missing required fields (Requirement 2)."""
    
    @pytest.mark.parametrize("field", [
        "headerId",
        "timestamp",
        "version",
        "manufacturer",
        "serialNumber",
    ])
    def test_missing_required_header_field(self, field):
        """Test that missing any required header field raises ValidationError."""
        payload = make_minimal_visualization()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            Visualization(**payload)
        
        error_message = str(exc_info.value)
        assert field in error_message.lower() or field in error_message
    
    def test_agv_position_missing_required_fields(self):
        """Test that agvPosition with missing required fields is rejected."""
        payload = make_minimal_visualization(
            agvPosition={
                "x": 10.0,
                # Missing: y, theta, mapId, positionInitialized
            }
        )
        
        with pytest.raises(ValidationError):
            Visualization(**payload)


# =============================================================================
# Requirement 3: Rejects Invalid Field Types or Formats
# =============================================================================

class TestVisualizationInvalidTypes:
    """Tests that Visualization rejects invalid field types (Requirement 3)."""
    
    @pytest.mark.parametrize("invalid_position", [
        "not_a_dict",
        123,
        ["list"],
        True,
    ])
    def test_invalid_agv_position_type(self, invalid_position):
        """Test that agvPosition must be a dict/object or None."""
        payload = make_minimal_visualization(agvPosition=invalid_position)
        
        with pytest.raises(ValidationError):
            Visualization(**payload)
    
    @pytest.mark.parametrize("invalid_velocity", [
        "not_a_dict",
        123,
        ["list"],
        True,
    ])
    def test_invalid_velocity_type(self, invalid_velocity):
        """Test that velocity must be a dict/object or None."""
        payload = make_minimal_visualization(velocity=invalid_velocity)
        
        with pytest.raises(ValidationError):
            Visualization(**payload)
    
    def test_invalid_agv_position_field_types(self):
        """Test that invalid types in AgvPosition fields are rejected."""
        payload = make_minimal_visualization(
            agvPosition={
                "x": "not_a_number",
                "y": 20.0,
                "theta": 1.57,
                "mapId": "map1",
                "positionInitialized": True,
            }
        )
        
        with pytest.raises(ValidationError):
            Visualization(**payload)


# =============================================================================
# Requirement 4: Handles Optional Fields Correctly
# =============================================================================

class TestVisualizationOptionalFields:
    """Tests that Visualization handles optional fields correctly (Requirement 4)."""
    
    def test_agv_position_is_optional(self):
        """Test that agvPosition is optional."""
        # Without agvPosition
        payload = make_minimal_visualization()
        msg = Visualization(**payload)
        assert msg.agvPosition is None
        
        # With agvPosition
        payload = make_minimal_visualization(agvPosition=make_agv_position())
        msg = Visualization(**payload)
        assert msg.agvPosition is not None
    
    def test_velocity_is_optional(self):
        """Test that velocity is optional."""
        # Without velocity
        payload = make_minimal_visualization()
        msg = Visualization(**payload)
        assert msg.velocity is None
        
        # With velocity
        payload = make_minimal_visualization(velocity=make_velocity())
        msg = Visualization(**payload)
        assert msg.velocity is not None
    
    def test_optional_fields_in_agv_position(self):
        """Test that optional fields in AgvPosition default to None."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position()
        )
        
        msg = Visualization(**payload)
        
        # Optional fields should be None
        assert msg.agvPosition.mapDescription is None
        assert msg.agvPosition.localizationScore is None
        assert msg.agvPosition.deviationRange is None
    
    def test_optional_fields_in_agv_position_can_be_set(self):
        """Test that optional AgvPosition fields can be explicitly set."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(
                mapDescription="Main floor",
                localizationScore=0.98,
                deviationRange=0.02
            )
        )
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition.mapDescription == "Main floor"
        assert msg.agvPosition.localizationScore == 0.98
        assert msg.agvPosition.deviationRange == 0.02
    
    def test_all_velocity_fields_are_optional(self):
        """Test that all Velocity fields are optional."""
        # Empty velocity
        payload = make_minimal_visualization(velocity={})
        msg = Visualization(**payload)
        
        assert msg.velocity.vx is None
        assert msg.velocity.vy is None
        assert msg.velocity.omega is None
    
    def test_partial_velocity_fields(self):
        """Test that Velocity fields can be set partially."""
        payload = make_minimal_visualization(
            velocity={"vx": 1.5}
        )
        
        msg = Visualization(**payload)
        
        assert msg.velocity.vx == 1.5
        assert msg.velocity.vy is None
        assert msg.velocity.omega is None


# =============================================================================
# Requirement 5: Validates Nested Objects and Arrays
# =============================================================================

class TestVisualizationNestedValidation:
    """Tests nested object validation (Requirement 5)."""
    
    def test_nested_agv_position_validation(self):
        """Test that nested AgvPosition object is validated."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position()
        )
        
        msg = Visualization(**payload)
        
        assert isinstance(msg.agvPosition, AgvPosition)
        assert msg.agvPosition.x == 10.5
        assert msg.agvPosition.positionInitialized is True
    
    def test_nested_velocity_validation(self):
        """Test that nested Velocity object is validated."""
        payload = make_minimal_visualization(
            velocity=make_velocity()
        )
        
        msg = Visualization(**payload)
        
        assert isinstance(msg.velocity, Velocity)
        assert msg.velocity.vx == 1.5
    
    def test_invalid_nested_agv_position(self):
        """Test that invalid AgvPosition is rejected."""
        payload = make_minimal_visualization(
            agvPosition={
                "x": 10.0,
                "y": 20.0,
                # Missing required fields: theta, mapId, positionInitialized
            }
        )
        
        with pytest.raises(ValidationError):
            Visualization(**payload)
    
    def test_agv_position_constraint_validation(self):
        """Test that AgvPosition field constraints are enforced."""
        # localizationScore must be 0.0-1.0
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(localizationScore=1.5)
        )
        
        with pytest.raises(ValidationError):
            Visualization(**payload)


# =============================================================================
# Requirement 6: Enforces Enum Values
# =============================================================================

class TestVisualizationEnumValidation:
    """Tests enum validation (Requirement 6)."""
    
    def test_no_enums_in_visualization(self):
        """Test that Visualization has no enum fields."""
        # Visualization model doesn't have enum fields
        # AgvPosition and Velocity also don't have enums
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(),
            velocity=make_velocity()
        )
        
        msg = Visualization(**payload)
        
        # No enum assertions - documenting that this model has no enums
        assert msg.agvPosition is not None
        assert msg.velocity is not None


# =============================================================================
# Requirement 7: Performs JSON Round-Trip
# =============================================================================

class TestVisualizationSerialization:
    """Tests JSON round-trip serialization (Requirement 7)."""
    
    def test_model_dump_json_round_trip_minimal(self):
        """Test serialization of minimal payload."""
        payload = make_minimal_visualization()
        
        original = Visualization(**payload)
        json_str = original.model_dump_json()
        reconstructed = Visualization.model_validate_json(json_str)
        
        assert reconstructed.headerId == original.headerId
        assert reconstructed.agvPosition is None
        assert reconstructed.velocity is None
    
    def test_model_dump_json_round_trip_with_position(self):
        """Test serialization with agvPosition."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(
                x=15.5,
                y=25.3,
                localizationScore=0.95
            )
        )
        
        original = Visualization(**payload)
        json_str = original.model_dump_json()
        reconstructed = Visualization.model_validate_json(json_str)
        
        assert reconstructed.agvPosition.x == original.agvPosition.x
        assert reconstructed.agvPosition.y == original.agvPosition.y
        assert reconstructed.agvPosition.localizationScore == 0.95
    
    def test_model_dump_json_round_trip_with_velocity(self):
        """Test serialization with velocity."""
        payload = make_minimal_visualization(
            velocity=make_velocity(vx=2.5, vy=-1.0, omega=0.3)
        )
        
        original = Visualization(**payload)
        json_str = original.model_dump_json()
        reconstructed = Visualization.model_validate_json(json_str)
        
        assert reconstructed.velocity.vx == 2.5
        assert reconstructed.velocity.vy == -1.0
        assert reconstructed.velocity.omega == 0.3
    
    def test_model_dump_json_round_trip_complete(self):
        """Test serialization with all fields."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(),
            velocity=make_velocity()
        )
        
        original = Visualization(**payload)
        reconstructed = Visualization.model_validate(original.model_dump())
        
        assert reconstructed.agvPosition.x == original.agvPosition.x
        assert reconstructed.velocity.vx == original.velocity.vx
    
    def test_to_mqtt_payload_round_trip(self):
        """Test MQTT payload serialization/deserialization."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position()
        )
        
        original = Visualization(**payload)
        mqtt_json = original.to_mqtt_payload()
        reconstructed = Visualization.from_mqtt_payload(mqtt_json)
        
        assert reconstructed.headerId == original.headerId
        assert reconstructed.agvPosition.mapId == original.agvPosition.mapId


# =============================================================================
# Requirement 8: Preserves Data Integrity
# =============================================================================

class TestVisualizationDataIntegrity:
    """Tests that Visualization preserves data integrity (Requirement 8)."""
    
    def test_float_precision_in_agv_position(self):
        """Test that float values in AgvPosition are preserved."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(
                x=123.456789,
                y=987.654321,
                theta=3.14159265,
                localizationScore=0.987654
            )
        )
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition.x == 123.456789
        assert msg.agvPosition.y == 987.654321
        assert msg.agvPosition.theta == 3.14159265
        assert msg.agvPosition.localizationScore == 0.987654
    
    def test_float_precision_in_velocity(self):
        """Test that float values in Velocity are preserved."""
        payload = make_minimal_visualization(
            velocity=make_velocity(
                vx=1.23456789,
                vy=-2.98765432,
                omega=0.12345678
            )
        )
        
        msg = Visualization(**payload)
        
        assert msg.velocity.vx == 1.23456789
        assert msg.velocity.vy == -2.98765432
        assert msg.velocity.omega == 0.12345678
    
    def test_boolean_values_preserved(self):
        """Test that boolean values are preserved."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(positionInitialized=False)
        )
        
        msg = Visualization(**payload)
        assert msg.agvPosition.positionInitialized is False
        
        # Round-trip test
        reconstructed = Visualization.model_validate(msg.model_dump())
        assert reconstructed.agvPosition.positionInitialized is False
    
    def test_none_values_preserved(self):
        """Test that None values in optional fields are preserved."""
        payload = make_minimal_visualization()
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition is None
        assert msg.velocity is None
        
        # Round-trip
        reconstructed = Visualization.model_validate_json(msg.model_dump_json())
        assert reconstructed.agvPosition is None
        assert reconstructed.velocity is None


# =============================================================================
# Requirement 9: Produces Clear Error Messages
# =============================================================================

class TestVisualizationErrorMessages:
    """Tests that Visualization produces clear error messages (Requirement 9)."""
    
    def test_missing_header_field_error(self):
        """Test that missing header field produces clear error."""
        payload = make_minimal_visualization()
        del payload["headerId"]
        
        with pytest.raises(ValidationError) as exc_info:
            Visualization(**payload)
        
        error_str = str(exc_info.value)
        assert "headerId" in error_str or "header_id" in error_str.lower()
    
    def test_invalid_nested_field_error(self):
        """Test that errors in nested objects reference the field path."""
        payload = make_minimal_visualization(
            agvPosition={
                "x": "not_a_number",
                "y": 20.0,
                "theta": 1.57,
                "mapId": "map1",
                "positionInitialized": True,
            }
        )
        
        with pytest.raises(ValidationError) as exc_info:
            Visualization(**payload)
        
        errors = exc_info.value.errors()
        
        # Should have location information
        for error in errors:
            assert "loc" in error
            # Location should include 'agvPosition'
            assert "agvPosition" in error["loc"] or "x" in error["loc"]
    
    def test_constraint_violation_error(self):
        """Test that constraint violations produce clear errors."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(localizationScore=2.0)  # > 1.0
        )
        
        with pytest.raises(ValidationError) as exc_info:
            Visualization(**payload)
        
        error_str = str(exc_info.value).lower()
        assert "localizationscore" in error_str or "score" in error_str


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestVisualizationEdgeCases:
    """Additional edge case tests for Visualization model."""
    
    def test_negative_coordinates(self):
        """Test that negative coordinates are accepted."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(x=-10.5, y=-20.3, theta=-1.57)
        )
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition.x == -10.5
        assert msg.agvPosition.y == -20.3
        assert msg.agvPosition.theta == -1.57
    
    def test_zero_values(self):
        """Test that zero values are accepted."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(x=0.0, y=0.0, theta=0.0),
            velocity=make_velocity(vx=0.0, vy=0.0, omega=0.0)
        )
        
        msg = Visualization(**payload)
        
        assert msg.agvPosition.x == 0.0
        assert msg.velocity.vx == 0.0
    
    def test_localization_score_boundaries(self):
        """Test that localizationScore boundaries are enforced."""
        # Valid boundaries
        for score in [0.0, 0.5, 1.0]:
            payload = make_minimal_visualization(
                agvPosition=make_agv_position(localizationScore=score)
            )
            msg = Visualization(**payload)
            assert msg.agvPosition.localizationScore == score
        
        # Invalid: > 1.0
        with pytest.raises(ValidationError):
            payload = make_minimal_visualization(
                agvPosition=make_agv_position(localizationScore=1.1)
            )
            Visualization(**payload)
        
        # Invalid: < 0.0
        with pytest.raises(ValidationError):
            payload = make_minimal_visualization(
                agvPosition=make_agv_position(localizationScore=-0.1)
            )
            Visualization(**payload)
    
    def test_special_characters_in_map_id(self):
        """Test that mapId accepts special characters."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(mapId="floor-1_section/A")
        )
        
        msg = Visualization(**payload)
        assert msg.agvPosition.mapId == "floor-1_section/A"
    
    def test_unicode_in_map_description(self):
        """Test that mapDescription accepts Unicode."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(
                mapDescription="仓库一楼 - Warehouse Floor 1 🏭"
            )
        )
        
        msg = Visualization(**payload)
        assert msg.agvPosition.mapDescription == "仓库一楼 - Warehouse Floor 1 🏭"
    
    def test_very_small_deviation_range(self):
        """Test that very small deviationRange values are accepted."""
        payload = make_minimal_visualization(
            agvPosition=make_agv_position(deviationRange=0.001)
        )
        
        msg = Visualization(**payload)
        assert msg.agvPosition.deviationRange == 0.001

