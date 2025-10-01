"""
Shared fixtures and helper functions for VDA5050 Pydantic model tests.

This module provides reusable test data and utilities for testing all VDA5050 models.
"""

from datetime import datetime
from typing import Any, Dict, List
from copy import deepcopy


# =============================================================================
# Timestamp Utilities
# =============================================================================

def get_valid_timestamps() -> List[str]:
    """Return list of valid ISO-8601 timestamp formats."""
    return [
        "2025-10-01T12:00:00Z",
        "2025-10-01T12:00:00.123Z",
        "2025-10-01T12:00:00.123456Z",
        "2025-10-01T12:00:00+00:00",
        "2025-10-01T12:00:00-05:00",
        "1991-03-11T11:40:03.12Z",
    ]


def get_invalid_timestamps() -> List[Any]:
    """Return list of invalid timestamp values that Pydantic cannot parse."""
    return [
        "12:00:00",  # Time only
        "2025/10/01 12:00:00",  # Wrong separators
        "invalid-timestamp",
        "",  # Empty string
        None,  # None
        "2025-13-01T12:00:00Z",  # Invalid month
        "2025-10-32T12:00:00Z",  # Invalid day
        "not a date",
    ]


# =============================================================================
# VDA5050Message Base Payload
# =============================================================================

def make_vda5050_header(**overrides) -> Dict[str, Any]:
    """Create minimal valid VDA5050Message header fields."""
    header = {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestManufacturer",
        "serialNumber": "AGV001",
    }
    header.update(overrides)
    return header


# =============================================================================
# Connection Model Fixtures
# =============================================================================

def make_minimal_connection(**overrides) -> Dict[str, Any]:
    """Create minimal valid Connection payload."""
    payload = make_vda5050_header()
    payload["connectionState"] = "ONLINE"
    payload.update(overrides)
    return payload


def get_connection_required_fields() -> List[str]:
    """Return list of required fields for Connection model."""
    return ["headerId", "timestamp", "version", "manufacturer", "serialNumber", "connectionState"]


# =============================================================================
# InstantActions Model Fixtures
# =============================================================================

def make_minimal_instant_actions(**overrides) -> Dict[str, Any]:
    """Create minimal valid InstantActions payload."""
    payload = make_vda5050_header()
    payload["actions"] = [
        {
            "actionId": "action_001",
            "actionType": "testAction",
            "blockingType": "NONE",
        }
    ]
    payload.update(overrides)
    return payload


def make_action(**overrides) -> Dict[str, Any]:
    """Create minimal valid Action object."""
    action = {
        "actionId": "action_001",
        "actionType": "pick",
        "blockingType": "SOFT",
    }
    action.update(overrides)
    return action


def make_action_parameter(**overrides) -> Dict[str, Any]:
    """Create minimal valid ActionParameter object."""
    param = {
        "key": "duration",
        "value": 5.0,
    }
    param.update(overrides)
    return param


# =============================================================================
# Visualization Model Fixtures
# =============================================================================

def make_minimal_visualization(**overrides) -> Dict[str, Any]:
    """Create minimal valid Visualization payload."""
    payload = make_vda5050_header()
    payload.update(overrides)
    return payload


def make_agv_position(**overrides) -> Dict[str, Any]:
    """Create minimal valid AgvPosition object."""
    position = {
        "x": 10.5,
        "y": 20.3,
        "theta": 1.57,
        "mapId": "warehouse_floor1",
        "positionInitialized": True,
    }
    position.update(overrides)
    return position


def make_velocity(**overrides) -> Dict[str, Any]:
    """Create minimal valid Velocity object."""
    velocity = {
        "vx": 1.5,
        "vy": 0.0,
        "omega": 0.1,
    }
    velocity.update(overrides)
    return velocity


# =============================================================================
# Order Model Fixtures
# =============================================================================

def make_minimal_order(**overrides) -> Dict[str, Any]:
    """Create minimal valid Order payload."""
    payload = make_vda5050_header()
    payload.update({
        "orderId": "order_001",
        "orderUpdateId": 0,
        "nodes": [make_node(nodeId="node_1", sequenceId=0)],
        "edges": [],
    })
    payload.update(overrides)
    return payload


def make_node(**overrides) -> Dict[str, Any]:
    """Create minimal valid Node object."""
    node = {
        "nodeId": "node_001",
        "sequenceId": 0,
        "released": True,
        "actions": [],
    }
    node.update(overrides)
    return node


def make_node_position(**overrides) -> Dict[str, Any]:
    """Create minimal valid NodePosition object."""
    position = {
        "x": 10.5,
        "y": 20.3,
        "mapId": "warehouse_floor1",
    }
    position.update(overrides)
    return position


def make_edge(**overrides) -> Dict[str, Any]:
    """Create minimal valid Edge object."""
    edge = {
        "edgeId": "edge_001",
        "sequenceId": 1,
        "released": True,
        "startNodeId": "node_001",
        "endNodeId": "node_002",
        "actions": [],
    }
    edge.update(overrides)
    return edge


def make_trajectory(**overrides) -> Dict[str, Any]:
    """Create minimal valid Trajectory object."""
    trajectory = {
        "degree": 1,
        "knotVector": [0.0, 0.0, 1.0, 1.0],
        "controlPoints": [
            {"x": 0.0, "y": 0.0},
            {"x": 10.0, "y": 10.0},
        ],
    }
    trajectory.update(overrides)
    return trajectory


def make_control_point(**overrides) -> Dict[str, Any]:
    """Create minimal valid ControlPoint object."""
    point = {
        "x": 5.0,
        "y": 3.0,
    }
    point.update(overrides)
    return point


# =============================================================================
# State Model Fixtures
# =============================================================================

def make_minimal_state(**overrides) -> Dict[str, Any]:
    """Create minimal valid State payload."""
    payload = make_vda5050_header()
    payload.update({
        "orderId": "order_001",
        "orderUpdateId": 0,
        "lastNodeId": "node_001",
        "lastNodeSequenceId": 0,
        "driving": False,
        "operatingMode": "AUTOMATIC",
        "nodeStates": [],
        "edgeStates": [],
        "actionStates": [],
        "batteryState": make_battery_state(),
        "errors": [],
        "safetyState": make_safety_state(),
    })
    payload.update(overrides)
    return payload


def make_node_state(**overrides) -> Dict[str, Any]:
    """Create minimal valid NodeState object."""
    node_state = {
        "nodeId": "node_001",
        "sequenceId": 0,
        "released": True,
    }
    node_state.update(overrides)
    return node_state


def make_edge_state(**overrides) -> Dict[str, Any]:
    """Create minimal valid EdgeState object."""
    edge_state = {
        "edgeId": "edge_001",
        "sequenceId": 1,
        "released": True,
    }
    edge_state.update(overrides)
    return edge_state


def make_action_state(**overrides) -> Dict[str, Any]:
    """Create minimal valid ActionState object."""
    action_state = {
        "actionId": "action_001",
        "actionStatus": "WAITING",
    }
    action_state.update(overrides)
    return action_state


def make_battery_state(**overrides) -> Dict[str, Any]:
    """Create minimal valid BatteryState object."""
    battery = {
        "batteryCharge": 80.0,
        "charging": False,
    }
    battery.update(overrides)
    return battery


def make_load(**overrides) -> Dict[str, Any]:
    """Create minimal valid Load object."""
    load = {}
    load.update(overrides)
    return load


def make_error(**overrides) -> Dict[str, Any]:
    """Create minimal valid Error object."""
    error = {
        "errorType": "navigationError",
        "errorLevel": "WARNING",
    }
    error.update(overrides)
    return error


def make_information(**overrides) -> Dict[str, Any]:
    """Create minimal valid Information object."""
    info = {
        "infoType": "debugInfo",
        "infoLevel": "INFO",
    }
    info.update(overrides)
    return info


def make_safety_state(**overrides) -> Dict[str, Any]:
    """Create minimal valid SafetyState object."""
    safety = {
        "eStop": "NONE",
        "fieldViolation": False,
    }
    safety.update(overrides)
    return safety


# =============================================================================
# Factsheet Model Fixtures
# =============================================================================

def make_minimal_factsheet(**overrides) -> Dict[str, Any]:
    """Create minimal valid Factsheet payload."""
    payload = make_vda5050_header()
    payload.update({
        "typeSpecification": make_type_specification(),
        "physicalParameters": make_physical_parameters(),
        "protocolLimits": make_protocol_limits(),
        "protocolFeatures": make_protocol_features(),
        "agvGeometry": make_agv_geometry(),
        "loadSpecification": make_load_specification(),
    })
    payload.update(overrides)
    return payload


def make_type_specification(**overrides) -> Dict[str, Any]:
    """Create minimal valid TypeSpecification object."""
    spec = {
        "seriesName": "TestSeries",
        "agvKinematic": "DIFF",
        "agvClass": "FORKLIFT",
        "maxLoadMass": 1000.0,
        "localizationTypes": ["NATURAL"],
        "navigationTypes": ["AUTONOMOUS"],
    }
    spec.update(overrides)
    return spec


def make_physical_parameters(**overrides) -> Dict[str, Any]:
    """Create minimal valid PhysicalParameters object."""
    params = {
        "speedMin": 0.0,
        "speedMax": 2.0,
        "accelerationMax": 1.0,
        "decelerationMax": 1.0,
        "heightMax": 2.0,
        "width": 1.0,
        "length": 1.5,
    }
    params.update(overrides)
    return params


def make_protocol_limits(**overrides) -> Dict[str, Any]:
    """Create minimal valid ProtocolLimits object."""
    limits = {
        "maxStringLens": {},
        "maxArrayLens": {},
        "timing": {
            "minOrderInterval": 1.0,
            "minStateInterval": 1.0,
        },
    }
    limits.update(overrides)
    return limits


def make_protocol_features(**overrides) -> Dict[str, Any]:
    """Create minimal valid ProtocolFeatures object."""
    features = {
        "optionalParameters": [],
        "agvActions": [],
    }
    features.update(overrides)
    return features


def make_agv_geometry(**overrides) -> Dict[str, Any]:
    """Create minimal valid AgvGeometry object."""
    geometry = {}
    geometry.update(overrides)
    return geometry


def make_load_specification(**overrides) -> Dict[str, Any]:
    """Create minimal valid LoadSpecification object."""
    spec = {}
    spec.update(overrides)
    return spec


def make_wheel_definition(**overrides) -> Dict[str, Any]:
    """Create minimal valid WheelDefinition object."""
    wheel = {
        "type": "DRIVE",
        "isActiveDriven": True,
        "isActiveSteered": False,
        "position": {"x": 0.5, "y": 0.3},
        "diameter": 0.2,
        "width": 0.05,
    }
    wheel.update(overrides)
    return wheel


def make_agv_action(**overrides) -> Dict[str, Any]:
    """Create minimal valid AgvAction object."""
    action = {
        "actionType": "pick",
        "actionScopes": ["NODE"],
    }
    action.update(overrides)
    return action


# =============================================================================
# Shared Nested Model Fixtures
# =============================================================================

def make_bounding_box_reference(**overrides) -> Dict[str, Any]:
    """Create minimal valid BoundingBoxReference object."""
    bbox = {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
    }
    bbox.update(overrides)
    return bbox


def make_load_dimensions(**overrides) -> Dict[str, Any]:
    """Create minimal valid LoadDimensions object."""
    dims = {
        "length": 1.2,
        "width": 0.8,
    }
    dims.update(overrides)
    return dims


# =============================================================================
# Utility Functions
# =============================================================================

def remove_field(payload: Dict[str, Any], field_path: str) -> Dict[str, Any]:
    """
    Remove a field from a nested dictionary.
    
    Args:
        payload: The dictionary to modify
        field_path: Dot-separated path to the field (e.g., 'batteryState.charging')
    
    Returns:
        Modified copy of the payload
    """
    result = deepcopy(payload)
    parts = field_path.split('.')
    
    if len(parts) == 1:
        result.pop(parts[0], None)
    else:
        current = result
        for part in parts[:-1]:
            if part in current:
                current = current[part]
            else:
                return result
        current.pop(parts[-1], None)
    
    return result


def set_field(payload: Dict[str, Any], field_path: str, value: Any) -> Dict[str, Any]:
    """
    Set a field in a nested dictionary.
    
    Args:
        payload: The dictionary to modify
        field_path: Dot-separated path to the field (e.g., 'batteryState.charging')
        value: The value to set
    
    Returns:
        Modified copy of the payload
    """
    result = deepcopy(payload)
    parts = field_path.split('.')
    
    if len(parts) == 1:
        result[parts[0]] = value
    else:
        current = result
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    
    return result


def get_all_enum_values() -> Dict[str, List[str]]:
    """Return all valid enum values for VDA5050 enums."""
    return {
        "ConnectionState": ["ONLINE", "OFFLINE", "CONNECTIONBROKEN"],
        "BlockingType": ["NONE", "SOFT", "HARD"],
        "OperatingMode": ["AUTOMATIC", "SEMIAUTOMATIC", "MANUAL", "SERVICE", "TEACHIN"],
        "ActionStatus": ["WAITING", "INITIALIZING", "RUNNING", "PAUSED", "FINISHED", "FAILED"],
        "ErrorLevel": ["WARNING", "FATAL"],
        "InfoLevel": ["INFO", "DEBUG"],
        "EStop": ["AUTOACK", "MANUAL", "REMOTE", "NONE"],
        "MapStatus": ["ENABLED", "DISABLED"],
        "AgvKinematic": ["DIFF", "OMNI", "THREEWHEEL"],
        "AgvClass": ["FORKLIFT", "CONVEYOR", "TUGGER", "CARRIER"],
        "LocalizationType": ["NATURAL", "REFLECTOR", "RFID", "DMC", "SPOT", "GRID"],
        "NavigationType": ["PHYSICAL_LINE_GUIDED", "VIRTUAL_LINE_GUIDED", "AUTONOMOUS"],
        "ActionScope": ["INSTANT", "NODE", "EDGE"],
        "ValueDataType": ["BOOL", "NUMBER", "INTEGER", "FLOAT", "STRING", "OBJECT", "ARRAY"],
        "Type": ["DRIVE", "CASTER", "FIXED", "MECANUM"],
        "Support": ["SUPPORTED", "REQUIRED"],
        "CorridorRefPoint": ["KINEMATICCENTER", "CONTOUR"],
    }


def get_invalid_enum_value() -> str:
    """Return a generic invalid enum value."""
    return "INVALID_ENUM_VALUE"

