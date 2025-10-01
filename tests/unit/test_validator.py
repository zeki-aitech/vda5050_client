# tests/unit/test_validator.py

import pytest
import json
from pathlib import Path
from jsonschema import ValidationError as JSONSchemaValidationError
from vda5050.validation.validator import MessageValidator
from vda5050.utils.exceptions import ValidationError as VDA5050ValidationError

# Directory where JSON Schemas are stored
# Three levels up from tests/unit → project root, then into src/vda5050/validation/schemas
SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "src" / "vda5050" / "validation" / "schemas"

@pytest.fixture
def validator():
    return MessageValidator(schema_dir=SCHEMAS_DIR)

def test_load_missing_schema(validator):
    with pytest.raises(VDA5050ValidationError) as exc:
        validator.validate_message("nonexistent", {})
    assert "Schema for 'nonexistent' not found" in str(exc.value)

def test_get_required_fields_connection(validator):
    required = validator.get_required_fields("connection")
    assert set(required) == {
        "headerId", "timestamp", "version",
        "manufacturer", "serialNumber", "connectionState"
    }

def test_get_schema_returns_dict(validator):
    schema = validator.get_schema("connection")
    assert isinstance(schema, dict)
    assert "properties" in schema and "required" in schema

def test_validate_message_valid_dict(validator):
    payload = {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "connectionState": "ONLINE"
    }
    assert validator.validate_message("connection", payload) is True

def test_validate_message_valid_str(validator):
    payload_str = json.dumps({
        "headerId": 2,
        "timestamp": "2025-10-01T13:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV002",
        "connectionState": "OFFLINE"
    })
    assert validator.validate_message("connection", payload_str) is True

def test_validate_message_missing_field(validator):
    payload = {
        # missing headerId
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "connectionState": "ONLINE"
    }
    with pytest.raises(VDA5050ValidationError) as exc:
        validator.validate_message("connection", payload)
    assert "headerId" in str(exc.value)

def test_validate_message_invalid_enum(validator):
    payload = {
        "headerId": 3,
        "timestamp": "2025-10-01T14:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV003",
        "connectionState": "INVALID"
    }
    with pytest.raises(VDA5050ValidationError) as exc:
        validator.validate_message("connection", payload)
    assert "INVALID" in str(exc.value)

def test_validate_message_malformed_json(validator):
    bad_json = "{bad json"
    with pytest.raises(VDA5050ValidationError) as exc:
        validator.validate_message("connection", bad_json)
    assert "Invalid JSON" in str(exc.value)

def test_schema_caching(monkeypatch, validator):
    load_calls = []
    original_load = json.load

    def spy_load(fp):
        load_calls.append(True)
        return original_load(fp)

    monkeypatch.setattr("vda5050.validation.validator.json.load", spy_load)
    # First load from file
    validator.get_schema("connection")
    # Second load should use cache, not reload file
    validator.get_schema("connection")
    assert len(load_calls) == 1


# ========== Parametrized tests for all schemas ==========

SCHEMAS = ["connection", "order", "state", "factsheet", "instantActions", "visualization"]

# Minimal valid payloads for each schema
VALID_PAYLOADS = {
    "connection": {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "connectionState": "ONLINE"
    },
    "order": {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "orderId": "O1",
        "orderUpdateId": 0,
        "nodes": [{"nodeId": "N1", "sequenceId": 1, "released": True, "actions": []}],
        "edges": []
    },
    "state": {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "orderId": "O1",
        "orderUpdateId": 0,
        "lastNodeId": "N1",
        "lastNodeSequenceId": 1,
        "nodeStates": [],
        "edgeStates": [],
        "driving": False,
        "actionStates": [],
        "batteryState": {"batteryCharge": 80.0, "charging": False},
        "operatingMode": "AUTOMATIC",
        "errors": [],
        "safetyState": {"eStop": "NONE", "fieldViolation": False}
    },
    "factsheet": {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "typeSpecification": {
            "seriesName": "TestSeries",
            "agvKinematic": "DIFF",
            "agvClass": "FORKLIFT",
            "maxLoadMass": 1000.0,
            "localizationTypes": ["NATURAL"],
            "navigationTypes": ["AUTONOMOUS"]
        },
        "physicalParameters": {
            "speedMin": 0.0,
            "speedMax": 2.0,
            "accelerationMax": 1.0,
            "decelerationMax": 1.0,
            "heightMax": 2.0,
            "width": 1.0,
            "length": 1.5
        },
        "protocolLimits": {
            "maxStringLens": {},
            "maxArrayLens": {},
            "timing": {
                "minOrderInterval": 1.0,
                "minStateInterval": 1.0
            }
        },
        "protocolFeatures": {
            "optionalParameters": [],
            "agvActions": []
        },
        "agvGeometry": {
            "wheelDefinitions": [],
            "envelopes2d": [],
            "envelopes3d": []
        },
        "loadSpecification": {
            "loadPositions": [],
            "loadSets": []
        }
    },
    "instantActions": {
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001",
        "actions": [
            {
                "actionId": "action1",
                "actionType": "testAction",
                "blockingType": "NONE"
            }
        ]
    },
    "visualization": {
        # Visualization has no required fields - all are optional
        "headerId": 1,
        "timestamp": "2025-10-01T12:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "AGV001"
    }
}


@pytest.mark.parametrize("message_type", SCHEMAS)
def test_validate_all_schemas_valid(validator, message_type):
    """Test that all schemas accept minimal valid payloads."""
    payload = VALID_PAYLOADS[message_type]
    assert validator.validate_message(message_type, payload) is True


@pytest.mark.parametrize("message_type", SCHEMAS)
def test_validate_all_schemas_missing_field(validator, message_type):
    """Test that all schemas reject payloads missing a required field."""
    required_fields = validator.get_required_fields(message_type)
    
    # Skip if no required fields (like visualization)
    if not required_fields:
        pytest.skip(f"Schema '{message_type}' has no required fields")
    
    # Create a copy of the valid payload
    payload = VALID_PAYLOADS[message_type].copy()
    
    # Remove the first required field
    missing_field = required_fields[0]
    payload.pop(missing_field, None)
    
    # Should raise validation error
    with pytest.raises(VDA5050ValidationError):
        validator.validate_message(message_type, payload)
