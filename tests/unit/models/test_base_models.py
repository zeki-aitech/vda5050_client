"""
Unit tests for VDA5050 base models and shared components.

Tests the foundation models used across all VDA5050 message types:
- VDA5050Message (base class for all messages)
- Action and ActionParameter
- BlockingType enum
- ControlPoint and Trajectory
- AgvPosition and Velocity
- BoundingBoxReference and LoadDimensions

These tests ensure the building blocks are solid before testing composed models.
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from vda5050.models.base import (
    VDA5050Message,
    Action,
    ActionParameter,
    BlockingType,
    ControlPoint,
    Trajectory,
    AgvPosition,
    Velocity,
    BoundingBoxReference,
    LoadDimensions,
)

from .fixtures import (
    make_vda5050_header,
    make_action,
    make_action_parameter,
    make_control_point,
    make_trajectory,
    make_agv_position,
    make_velocity,
    make_bounding_box_reference,
    make_load_dimensions,
    get_valid_timestamps,
    get_invalid_timestamps,
    remove_field,
    set_field,
)


# =============================================================================
# VDA5050Message Base Class Tests
# =============================================================================

class TestVDA5050Message:
    """Tests for the VDA5050Message base class."""
    
    def test_valid_minimal_header(self):
        """Test that VDA5050Message accepts minimal valid header."""
        # VDA5050Message is abstract, but we can test it through a concrete subclass
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header()
        payload["connectionState"] = "ONLINE"
        
        msg = Connection(**payload)
        assert msg.headerId == 1
        assert msg.version == "2.1.0"
        assert msg.manufacturer == "TestManufacturer"
        assert msg.serialNumber == "AGV001"
    
    @pytest.mark.parametrize("field", [
        "headerId", "timestamp", "version", "manufacturer", "serialNumber"
    ])
    def test_missing_required_header_field(self, field):
        """Test that missing any required header field raises ValidationError."""
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header()
        payload["connectionState"] = "ONLINE"
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        assert field in str(exc_info.value)
    
    @pytest.mark.parametrize("timestamp", get_valid_timestamps())
    def test_valid_timestamp_formats(self, timestamp):
        """Test that all valid ISO-8601 timestamp formats are accepted."""
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header(timestamp=timestamp)
        payload["connectionState"] = "ONLINE"
        
        msg = Connection(**payload)
        assert isinstance(msg.timestamp, datetime)
    
    @pytest.mark.parametrize("invalid_timestamp", get_invalid_timestamps())
    def test_invalid_timestamp_formats(self, invalid_timestamp):
        """Test that invalid timestamp formats are rejected."""
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header(timestamp=invalid_timestamp)
        payload["connectionState"] = "ONLINE"
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        # Check that error mentions timestamp field
        error_str = str(exc_info.value).lower()
        assert "timestamp" in error_str
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("headerId", "not_an_int"),
        ("headerId", 3.14),
        ("headerId", None),
        ("version", 123),
        ("version", None),
        ("manufacturer", 123),
        ("manufacturer", None),
        ("serialNumber", 123),
        ("serialNumber", None),
    ])
    def test_invalid_header_field_types(self, field, invalid_value):
        """Test that wrong types for header fields are rejected."""
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header()
        payload["connectionState"] = "ONLINE"
        payload[field] = invalid_value
        
        with pytest.raises(ValidationError) as exc_info:
            Connection(**payload)
        assert field in str(exc_info.value)
    
    def test_to_mqtt_payload(self):
        """Test serialization to MQTT JSON payload."""
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header()
        payload["connectionState"] = "ONLINE"
        
        msg = Connection(**payload)
        json_str = msg.to_mqtt_payload()
        
        assert isinstance(json_str, str)
        assert "headerId" in json_str
        assert "connectionState" in json_str
    
    def test_from_mqtt_payload(self):
        """Test deserialization from MQTT JSON payload."""
        from vda5050.models.connection import Connection
        
        payload = make_vda5050_header()
        payload["connectionState"] = "ONLINE"
        
        original = Connection(**payload)
        json_str = original.to_mqtt_payload()
        reconstructed = Connection.from_mqtt_payload(json_str)
        
        assert reconstructed.headerId == original.headerId
        assert reconstructed.connectionState == original.connectionState


# =============================================================================
# BlockingType Enum Tests
# =============================================================================

class TestBlockingType:
    """Tests for the BlockingType enum."""
    
    @pytest.mark.parametrize("value", ["NONE", "SOFT", "HARD"])
    def test_valid_blocking_types(self, value):
        """Test that all valid BlockingType values are accepted."""
        blocking_type = BlockingType(value)
        assert blocking_type.value == value
    
    def test_invalid_blocking_type(self):
        """Test that invalid BlockingType values are rejected."""
        with pytest.raises(ValueError):
            BlockingType("INVALID")


# =============================================================================
# ActionParameter Tests
# =============================================================================

class TestActionParameter:
    """Tests for the ActionParameter model."""
    
    def test_valid_minimal_action_parameter(self):
        """Test that ActionParameter accepts minimal valid payload."""
        payload = make_action_parameter()
        
        param = ActionParameter(**payload)
        assert param.key == "duration"
        assert param.value == 5.0
    
    @pytest.mark.parametrize("field", ["key", "value"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_action_parameter()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            ActionParameter(**payload)
        assert field in str(exc_info.value)
    
    @pytest.mark.parametrize("value,expected_type", [
        (5.0, float),
        ("text", str),
        (True, bool),
        ([1, 2, 3], list),
        ({"nested": "value"}, dict),
    ])
    def test_various_value_types(self, value, expected_type):
        """Test that ActionParameter accepts various value types."""
        payload = make_action_parameter(value=value)
        
        param = ActionParameter(**payload)
        assert isinstance(param.value, expected_type)
        assert param.value == value
    
    def test_json_round_trip(self):
        """Test JSON serialization and deserialization preserves data."""
        payload = make_action_parameter(key="testKey", value=[1, 2, 3])
        
        original = ActionParameter(**payload)
        json_str = original.model_dump_json()
        reconstructed = ActionParameter.model_validate_json(json_str)
        
        assert reconstructed.key == original.key
        assert reconstructed.value == original.value


# =============================================================================
# Action Tests
# =============================================================================

class TestAction:
    """Tests for the Action model."""
    
    def test_valid_minimal_action(self):
        """Test that Action accepts minimal valid payload."""
        payload = make_action()
        
        action = Action(**payload)
        assert action.actionId == "action_001"
        assert action.actionType == "pick"
        assert action.blockingType == BlockingType.SOFT
    
    @pytest.mark.parametrize("field", ["actionType", "actionId", "blockingType"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_action()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            Action(**payload)
        assert field in str(exc_info.value)
    
    def test_optional_action_description(self):
        """Test that actionDescription is optional."""
        # Without description
        payload = make_action()
        action = Action(**payload)
        assert action.actionDescription is None
        
        # With description
        payload = make_action(actionDescription="Pick up the load")
        action = Action(**payload)
        assert action.actionDescription == "Pick up the load"
    
    def test_optional_action_parameters(self):
        """Test that actionParameters is optional."""
        # Without parameters
        payload = make_action()
        action = Action(**payload)
        assert action.actionParameters is None
        
        # With parameters
        payload = make_action(actionParameters=[
            make_action_parameter(key="duration", value=5.0),
            make_action_parameter(key="direction", value="left"),
        ])
        action = Action(**payload)
        assert len(action.actionParameters) == 2
        assert action.actionParameters[0].key == "duration"
    
    @pytest.mark.parametrize("blocking_type", ["NONE", "SOFT", "HARD"])
    def test_valid_blocking_types(self, blocking_type):
        """Test that all valid BlockingType enum values are accepted."""
        payload = make_action(blockingType=blocking_type)
        
        action = Action(**payload)
        assert action.blockingType.value == blocking_type
    
    def test_invalid_blocking_type(self):
        """Test that invalid BlockingType values are rejected."""
        payload = make_action(blockingType="INVALID")
        
        with pytest.raises(ValidationError) as exc_info:
            Action(**payload)
        assert "blockingType" in str(exc_info.value)
    
    def test_nested_action_parameters_validation(self):
        """Test that nested ActionParameter objects are validated."""
        payload = make_action(actionParameters=[
            {"key": "validKey", "value": 123},
            {"key": "missingValue"},  # Invalid: missing value
        ])
        
        with pytest.raises(ValidationError):
            Action(**payload)
    
    def test_json_round_trip(self):
        """Test JSON serialization preserves all data."""
        payload = make_action(
            actionDescription="Test action",
            actionParameters=[
                make_action_parameter(key="param1", value=10),
                make_action_parameter(key="param2", value="test"),
            ]
        )
        
        original = Action(**payload)
        json_str = original.model_dump_json()
        reconstructed = Action.model_validate_json(json_str)
        
        assert reconstructed.actionId == original.actionId
        assert reconstructed.actionType == original.actionType
        assert reconstructed.blockingType == original.blockingType
        assert len(reconstructed.actionParameters) == 2


# =============================================================================
# ControlPoint Tests
# =============================================================================

class TestControlPoint:
    """Tests for the ControlPoint model."""
    
    def test_valid_minimal_control_point(self):
        """Test that ControlPoint accepts minimal valid payload."""
        payload = make_control_point()
        
        point = ControlPoint(**payload)
        assert point.x == 5.0
        assert point.y == 3.0
        assert point.weight is None
    
    @pytest.mark.parametrize("field", ["x", "y"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_control_point()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            ControlPoint(**payload)
        assert field in str(exc_info.value)
    
    def test_optional_weight_field(self):
        """Test that weight field is optional and can be set."""
        # Without weight
        payload = make_control_point()
        point = ControlPoint(**payload)
        assert point.weight is None
        
        # With weight
        payload = make_control_point(weight=2.5)
        point = ControlPoint(**payload)
        assert point.weight == 2.5
    
    def test_weight_must_be_non_negative(self):
        """Test that weight must be >= 0.0."""
        payload = make_control_point(weight=-1.0)
        
        with pytest.raises(ValidationError) as exc_info:
            ControlPoint(**payload)
        assert "weight" in str(exc_info.value)
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("x", "not_a_number"),
        ("y", "not_a_number"),
        ("x", None),
        ("y", None),
    ])
    def test_invalid_field_types(self, field, invalid_value):
        """Test that wrong types are rejected."""
        payload = make_control_point()
        payload[field] = invalid_value
        
        with pytest.raises(ValidationError):
            ControlPoint(**payload)
    
    def test_data_integrity(self):
        """Test that float values are preserved accurately."""
        payload = make_control_point(x=10.123456, y=20.987654, weight=1.5)
        
        point = ControlPoint(**payload)
        assert point.x == 10.123456
        assert point.y == 20.987654
        assert point.weight == 1.5


# =============================================================================
# Trajectory Tests
# =============================================================================

class TestTrajectory:
    """Tests for the Trajectory model."""
    
    def test_valid_minimal_trajectory(self):
        """Test that Trajectory accepts minimal valid payload."""
        payload = make_trajectory()
        
        traj = Trajectory(**payload)
        assert traj.degree == 1
        assert len(traj.knotVector) == 4
        assert len(traj.controlPoints) == 2
    
    @pytest.mark.parametrize("field", ["degree", "knotVector", "controlPoints"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_trajectory()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            Trajectory(**payload)
        assert field in str(exc_info.value)
    
    def test_degree_must_be_at_least_one(self):
        """Test that degree must be >= 1."""
        payload = make_trajectory(degree=0)
        
        with pytest.raises(ValidationError) as exc_info:
            Trajectory(**payload)
        assert "degree" in str(exc_info.value)
    
    def test_knot_vector_values_in_range(self):
        """Test that knotVector values must be between 0.0 and 1.0."""
        # Invalid: value > 1.0
        payload = make_trajectory(knotVector=[0.0, 0.0, 1.5, 1.5])
        with pytest.raises(ValidationError):
            Trajectory(**payload)
        
        # Invalid: value < 0.0
        payload = make_trajectory(knotVector=[-0.5, 0.0, 1.0, 1.0])
        with pytest.raises(ValidationError):
            Trajectory(**payload)
    
    def test_control_points_array_validation(self):
        """Test that controlPoints array is validated."""
        # Valid control points
        payload = make_trajectory(controlPoints=[
            {"x": 0.0, "y": 0.0},
            {"x": 5.0, "y": 5.0},
            {"x": 10.0, "y": 10.0},
        ])
        traj = Trajectory(**payload)
        assert len(traj.controlPoints) == 3
        
        # Invalid control point (missing y)
        payload = make_trajectory(controlPoints=[
            {"x": 0.0},
        ])
        with pytest.raises(ValidationError):
            Trajectory(**payload)
    
    def test_json_round_trip(self):
        """Test JSON serialization preserves all data."""
        payload = make_trajectory(
            degree=2,
            knotVector=[0.0, 0.0, 0.0, 0.5, 1.0, 1.0, 1.0],
            controlPoints=[
                {"x": 0.0, "y": 0.0, "weight": 1.0},
                {"x": 5.0, "y": 5.0, "weight": 2.0},
                {"x": 10.0, "y": 10.0, "weight": 1.0},
                {"x": 15.0, "y": 5.0, "weight": 1.0},
            ]
        )
        
        original = Trajectory(**payload)
        json_str = original.model_dump_json()
        reconstructed = Trajectory.model_validate_json(json_str)
        
        assert reconstructed.degree == original.degree
        assert reconstructed.knotVector == original.knotVector
        assert len(reconstructed.controlPoints) == 4


# =============================================================================
# AgvPosition Tests
# =============================================================================

class TestAgvPosition:
    """Tests for the AgvPosition model."""
    
    def test_valid_minimal_agv_position(self):
        """Test that AgvPosition accepts minimal valid payload."""
        payload = make_agv_position()
        
        pos = AgvPosition(**payload)
        assert pos.x == 10.5
        assert pos.y == 20.3
        assert pos.theta == 1.57
        assert pos.mapId == "warehouse_floor1"
        assert pos.positionInitialized is True
    
    @pytest.mark.parametrize("field", ["x", "y", "theta", "mapId", "positionInitialized"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_agv_position()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            AgvPosition(**payload)
        assert field in str(exc_info.value)
    
    def test_optional_fields(self):
        """Test that optional fields default to None."""
        payload = make_agv_position()
        
        pos = AgvPosition(**payload)
        assert pos.mapDescription is None
        assert pos.localizationScore is None
        assert pos.deviationRange is None
    
    def test_optional_fields_can_be_set(self):
        """Test that optional fields can be explicitly set."""
        payload = make_agv_position(
            mapDescription="Main warehouse floor",
            localizationScore=0.95,
            deviationRange=0.05
        )
        
        pos = AgvPosition(**payload)
        assert pos.mapDescription == "Main warehouse floor"
        assert pos.localizationScore == 0.95
        assert pos.deviationRange == 0.05
    
    def test_localization_score_range(self):
        """Test that localizationScore must be between 0.0 and 1.0."""
        # Valid values
        for score in [0.0, 0.5, 1.0]:
            payload = make_agv_position(localizationScore=score)
            pos = AgvPosition(**payload)
            assert pos.localizationScore == score
        
        # Invalid: > 1.0
        payload = make_agv_position(localizationScore=1.5)
        with pytest.raises(ValidationError):
            AgvPosition(**payload)
        
        # Invalid: < 0.0
        payload = make_agv_position(localizationScore=-0.1)
        with pytest.raises(ValidationError):
            AgvPosition(**payload)
    
    def test_data_integrity(self):
        """Test that float and boolean values are preserved."""
        payload = make_agv_position(
            x=123.456789,
            y=987.654321,
            theta=3.14159,
            positionInitialized=False
        )
        
        pos = AgvPosition(**payload)
        assert pos.x == 123.456789
        assert pos.y == 987.654321
        assert pos.theta == 3.14159
        assert pos.positionInitialized is False


# =============================================================================
# Velocity Tests
# =============================================================================

class TestVelocity:
    """Tests for the Velocity model."""
    
    def test_valid_velocity_all_optional(self):
        """Test that all Velocity fields are optional."""
        # Empty velocity
        vel = Velocity()
        assert vel.vx is None
        assert vel.vy is None
        assert vel.omega is None
    
    def test_velocity_fields_can_be_set(self):
        """Test that velocity fields can be explicitly set."""
        payload = make_velocity(vx=1.5, vy=0.5, omega=0.2)
        
        vel = Velocity(**payload)
        assert vel.vx == 1.5
        assert vel.vy == 0.5
        assert vel.omega == 0.2
    
    def test_partial_velocity_fields(self):
        """Test that velocity fields can be set partially."""
        vel = Velocity(vx=1.0)
        assert vel.vx == 1.0
        assert vel.vy is None
        assert vel.omega is None
    
    def test_negative_velocities_allowed(self):
        """Test that negative velocity values are allowed."""
        payload = make_velocity(vx=-1.5, vy=-0.5, omega=-0.2)
        
        vel = Velocity(**payload)
        assert vel.vx == -1.5
        assert vel.vy == -0.5
        assert vel.omega == -0.2
    
    def test_data_integrity(self):
        """Test that float values are preserved accurately."""
        payload = make_velocity(vx=1.123456, vy=2.987654, omega=0.314159)
        
        vel = Velocity(**payload)
        assert vel.vx == 1.123456
        assert vel.vy == 2.987654
        assert vel.omega == 0.314159


# =============================================================================
# BoundingBoxReference Tests
# =============================================================================

class TestBoundingBoxReference:
    """Tests for the BoundingBoxReference model."""
    
    def test_valid_minimal_bounding_box(self):
        """Test that BoundingBoxReference accepts minimal valid payload."""
        payload = make_bounding_box_reference()
        
        bbox = BoundingBoxReference(**payload)
        assert bbox.x == 0.0
        assert bbox.y == 0.0
        assert bbox.z == 0.0
        assert bbox.theta is None
    
    @pytest.mark.parametrize("field", ["x", "y", "z"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_bounding_box_reference()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            BoundingBoxReference(**payload)
        assert field in str(exc_info.value)
    
    def test_optional_theta_field(self):
        """Test that theta field is optional."""
        # Without theta
        payload = make_bounding_box_reference()
        bbox = BoundingBoxReference(**payload)
        assert bbox.theta is None
        
        # With theta
        payload = make_bounding_box_reference(theta=1.57)
        bbox = BoundingBoxReference(**payload)
        assert bbox.theta == 1.57


# =============================================================================
# LoadDimensions Tests
# =============================================================================

class TestLoadDimensions:
    """Tests for the LoadDimensions model."""
    
    def test_valid_minimal_load_dimensions(self):
        """Test that LoadDimensions accepts minimal valid payload."""
        payload = make_load_dimensions()
        
        dims = LoadDimensions(**payload)
        assert dims.length == 1.2
        assert dims.width == 0.8
        assert dims.height is None
    
    @pytest.mark.parametrize("field", ["length", "width"])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_load_dimensions()
        del payload[field]
        
        with pytest.raises(ValidationError) as exc_info:
            LoadDimensions(**payload)
        assert field in str(exc_info.value)
    
    def test_optional_height_field(self):
        """Test that height field is optional."""
        # Without height
        payload = make_load_dimensions()
        dims = LoadDimensions(**payload)
        assert dims.height is None
        
        # With height
        payload = make_load_dimensions(height=1.5)
        dims = LoadDimensions(**payload)
        assert dims.height == 1.5
    
    def test_json_round_trip(self):
        """Test JSON serialization preserves all data."""
        payload = make_load_dimensions(length=2.0, width=1.0, height=1.5)
        
        original = LoadDimensions(**payload)
        json_str = original.model_dump_json()
        reconstructed = LoadDimensions.model_validate_json(json_str)
        
        assert reconstructed.length == original.length
        assert reconstructed.width == original.width
        assert reconstructed.height == original.height

