"""
Unit tests for the VDA5050 State message model.

The State message reports the current AGV state including position, velocity,
battery, errors, safety state, and action/node/edge states.

Tests verify all 9 Pydantic model validation requirements.
"""

import pytest
from pydantic import ValidationError

from vda5050.models.state import (
    State, OperatingMode, ActionStatus, ErrorLevel, InfoLevel, EStop
)

from .fixtures import (
    make_minimal_state,
    make_node_state,
    make_edge_state,
    make_action_state,
    make_battery_state,
    make_error,
    make_information,
    make_safety_state,
    make_agv_position,
    make_velocity,
)


class TestStateValidPayloads:
    """Test that State accepts valid payloads (Requirement 1)."""
    
    def test_minimal_valid_state(self):
        """Test minimal valid State."""
        payload = make_minimal_state()
        
        state = State(**payload)
        
        assert state.orderId == "order_001"
        assert state.orderUpdateId == 0
        assert state.lastNodeId == "node_001"
        assert state.lastNodeSequenceId == 0
        assert state.driving is False
        assert state.operatingMode == OperatingMode.AUTOMATIC
        assert len(state.nodeStates) == 0
        assert len(state.edgeStates) == 0
        assert len(state.actionStates) == 0
        assert len(state.errors) == 0
        assert state.batteryState.batteryCharge == 80.0
        assert state.safetyState.eStop == EStop.NONE
    
    def test_state_with_position_and_velocity(self):
        """Test State with position and velocity."""
        payload = make_minimal_state(
            agvPosition=make_agv_position(),
            velocity=make_velocity()
        )
        
        state = State(**payload)
        assert state.agvPosition is not None
        assert state.velocity is not None
    
    def test_state_with_all_arrays_populated(self):
        """Test State with all arrays populated."""
        payload = make_minimal_state(
            nodeStates=[make_node_state(nodeId="n1"), make_node_state(nodeId="n2")],
            edgeStates=[make_edge_state(edgeId="e1")],
            actionStates=[make_action_state(actionId="a1")],
            errors=[make_error(errorType="testError")],
            information=[make_information(infoType="testInfo")],
        )
        
        state = State(**payload)
        assert len(state.nodeStates) == 2
        assert len(state.edgeStates) == 1
        assert len(state.actionStates) == 1
        assert len(state.errors) == 1
        assert len(state.information) == 1


class TestStateMissingFields:
    """Test that State rejects missing required fields (Requirement 2)."""
    
    @pytest.mark.parametrize("field", [
        "orderId", "orderUpdateId", "lastNodeId", "lastNodeSequenceId",
        "driving", "operatingMode", "nodeStates", "edgeStates",
        "actionStates", "batteryState", "errors", "safetyState"
    ])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_minimal_state()
        del payload[field]
        
        with pytest.raises(ValidationError):
            State(**payload)
    
    def test_battery_state_missing_required_fields(self):
        """Test that batteryState with missing required fields is rejected."""
        payload = make_minimal_state(
            batteryState={"batteryCharge": 80.0}  # Missing charging
        )
        
        with pytest.raises(ValidationError):
            State(**payload)


class TestStateInvalidTypes:
    """Test that State rejects invalid field types (Requirement 3)."""
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("orderId", 123),
        ("orderUpdateId", "not_int"),
        ("lastNodeId", 456),
        ("lastNodeSequenceId", "not_int"),
        ("driving", "not_bool"),
        ("nodeStates", "not_list"),
        ("edgeStates", "not_list"),
    ])
    def test_invalid_field_types(self, field, invalid_value):
        """Test that invalid types are rejected."""
        payload = make_minimal_state()
        payload[field] = invalid_value
        
        with pytest.raises(ValidationError):
            State(**payload)


class TestStateOptionalFields:
    """Test that State handles optional fields correctly (Requirement 4)."""
    
    def test_optional_fields_default_to_none(self):
        """Test that optional fields default to None."""
        payload = make_minimal_state()
        state = State(**payload)
        
        assert state.zoneSetId is None
        assert state.paused is None
        assert state.newBaseRequest is None
        assert state.distanceSinceLastNode is None
        assert state.agvPosition is None
        assert state.velocity is None
        assert state.loads is None
        assert state.information is None
    
    def test_optional_fields_can_be_set(self):
        """Test that optional fields can be set."""
        payload = make_minimal_state(
            zoneSetId="zone_1",
            paused=True,
            newBaseRequest=False,
            distanceSinceLastNode=5.5,
            loads=[{"loadId": "LOAD_1"}]
        )
        
        state = State(**payload)
        assert state.zoneSetId == "zone_1"
        assert state.paused is True
        assert state.distanceSinceLastNode == 5.5


class TestStateNestedValidation:
    """Test nested object and array validation (Requirement 5)."""
    
    def test_nested_battery_state_validation(self):
        """Test that BatteryState is validated."""
        payload = make_minimal_state(
            batteryState=make_battery_state(
                batteryCharge=75.5,
                batteryVoltage=48.0,
                charging=True,
                reach=1000.0
            )
        )
        
        state = State(**payload)
        assert state.batteryState.batteryCharge == 75.5
        assert state.batteryState.batteryVoltage == 48.0
    
    def test_nested_safety_state_validation(self):
        """Test that SafetyState is validated."""
        payload = make_minimal_state(
            safetyState=make_safety_state(eStop="MANUAL", fieldViolation=True)
        )
        
        state = State(**payload)
        assert state.safetyState.eStop == EStop.MANUAL
        assert state.safetyState.fieldViolation is True
    
    def test_nested_arrays_validation(self):
        """Test that array elements are validated."""
        payload = make_minimal_state(
            nodeStates=[
                make_node_state(nodeId="n1", sequenceId=0, released=True)
            ],
            actionStates=[
                make_action_state(actionId="a1", actionStatus="RUNNING")
            ]
        )
        
        state = State(**payload)
        assert state.nodeStates[0].nodeId == "n1"
        assert state.actionStates[0].actionStatus == ActionStatus.RUNNING


class TestStateEnumValidation:
    """Test enum value enforcement (Requirement 6)."""
    
    @pytest.mark.parametrize("mode", [
        "AUTOMATIC", "SEMIAUTOMATIC", "MANUAL", "SERVICE", "TEACHIN"
    ])
    def test_valid_operating_modes(self, mode):
        """Test that all valid OperatingMode values are accepted."""
        payload = make_minimal_state(operatingMode=mode)
        
        state = State(**payload)
        assert state.operatingMode.value == mode
    
    @pytest.mark.parametrize("status", [
        "WAITING", "INITIALIZING", "RUNNING", "PAUSED", "FINISHED", "FAILED"
    ])
    def test_valid_action_statuses(self, status):
        """Test that all valid ActionStatus values are accepted."""
        payload = make_minimal_state(
            actionStates=[make_action_state(actionStatus=status)]
        )
        
        state = State(**payload)
        assert state.actionStates[0].actionStatus.value == status
    
    @pytest.mark.parametrize("level", ["WARNING", "FATAL"])
    def test_valid_error_levels(self, level):
        """Test that all valid ErrorLevel values are accepted."""
        payload = make_minimal_state(
            errors=[make_error(errorLevel=level)]
        )
        
        state = State(**payload)
        assert state.errors[0].errorLevel.value == level
    
    @pytest.mark.parametrize("estop", ["AUTOACK", "MANUAL", "REMOTE", "NONE"])
    def test_valid_estop_values(self, estop):
        """Test that all valid EStop values are accepted."""
        payload = make_minimal_state(
            safetyState=make_safety_state(eStop=estop)
        )
        
        state = State(**payload)
        assert state.safetyState.eStop.value == estop


class TestStateSerialization:
    """Test JSON round-trip serialization (Requirement 7)."""
    
    def test_model_dump_json_round_trip(self):
        """Test serialization preserves all data."""
        payload = make_minimal_state(
            orderId="order_123",
            driving=True,
            operatingMode="MANUAL",
            batteryState=make_battery_state(batteryCharge=50.0),
            actionStates=[make_action_state(actionId="a1")]
        )
        
        original = State(**payload)
        json_str = original.model_dump_json()
        reconstructed = State.model_validate_json(json_str)
        
        assert reconstructed.orderId == original.orderId
        assert reconstructed.driving == original.driving
        assert len(reconstructed.actionStates) == 1


class TestStateDataIntegrity:
    """Test data integrity preservation (Requirement 8)."""
    
    def test_array_order_preserved(self):
        """Test that array order is preserved."""
        payload = make_minimal_state(
            actionStates=[
                make_action_state(actionId="first"),
                make_action_state(actionId="second"),
                make_action_state(actionId="third"),
            ]
        )
        
        state = State(**payload)
        assert state.actionStates[0].actionId == "first"
        assert state.actionStates[1].actionId == "second"
        assert state.actionStates[2].actionId == "third"
    
    def test_float_precision_preserved(self):
        """Test that float precision is maintained."""
        payload = make_minimal_state(
            batteryState=make_battery_state(
                batteryCharge=75.123456,
                batteryVoltage=48.987654
            ),
            distanceSinceLastNode=123.456789
        )
        
        state = State(**payload)
        assert state.batteryState.batteryCharge == 75.123456
        assert state.distanceSinceLastNode == 123.456789
    
    def test_boolean_values_preserved(self):
        """Test that boolean values are preserved."""
        payload = make_minimal_state(
            driving=True,
            paused=False,
            safetyState=make_safety_state(fieldViolation=True)
        )
        
        state = State(**payload)
        assert state.driving is True
        assert state.paused is False
        assert state.safetyState.fieldViolation is True


class TestStateErrorMessages:
    """Test clear error message generation (Requirement 9)."""
    
    def test_missing_field_error_clarity(self):
        """Test that missing fields produce clear errors."""
        payload = make_minimal_state()
        del payload["batteryState"]
        
        with pytest.raises(ValidationError) as exc_info:
            State(**payload)
        
        error_str = str(exc_info.value)
        assert "batteryState" in error_str or "battery" in error_str.lower()
    
    def test_invalid_enum_error_clarity(self):
        """Test that invalid enum values produce clear errors."""
        payload = make_minimal_state(operatingMode="INVALID_MODE")
        
        with pytest.raises(ValidationError) as exc_info:
            State(**payload)
        
        error_str = str(exc_info.value)
        assert "operatingMode" in error_str or "operating" in error_str.lower()


class TestStateEdgeCases:
    """Additional edge case tests."""
    
    def test_empty_string_fields(self):
        """Test that empty string values are handled."""
        payload = make_minimal_state(orderId="", lastNodeId="")
        
        state = State(**payload)
        assert state.orderId == ""
        assert state.lastNodeId == ""
    
    def test_battery_charge_boundaries(self):
        """Test battery charge value range."""
        # Valid values
        for charge in [0.0, 50.0, 100.0]:
            payload = make_minimal_state(
                batteryState=make_battery_state(batteryCharge=charge)
            )
            state = State(**payload)
            assert state.batteryState.batteryCharge == charge
    
    def test_complex_state_with_all_fields(self):
        """Test State with maximum complexity."""
        payload = make_minimal_state(
            zoneSetId="zone_1",
            paused=True,
            newBaseRequest=False,
            distanceSinceLastNode=10.5,
            agvPosition=make_agv_position(),
            velocity=make_velocity(),
            nodeStates=[make_node_state()],
            edgeStates=[make_edge_state()],
            actionStates=[make_action_state()],
            loads=[{"loadId": "L1", "loadType": "pallet"}],
            errors=[make_error()],
            information=[make_information()],
        )
        
        state = State(**payload)
        assert state.zoneSetId == "zone_1"
        assert state.agvPosition is not None
        assert len(state.loads) == 1

