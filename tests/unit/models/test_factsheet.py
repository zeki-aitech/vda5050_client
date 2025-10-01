"""
Unit tests for the VDA5050 Factsheet message model.

The Factsheet message describes the AGV's capabilities, physical parameters,
protocol limits, and supported features. It is the most complex VDA5050 message
with deep nesting.

Tests verify all 9 Pydantic model validation requirements.
"""

import pytest
from pydantic import ValidationError

from vda5050.models.factsheet import (
    Factsheet,
    AgvKinematic, AgvClass, LocalizationType, NavigationType,
    Support, ActionScope, ValueDataType, Type as WheelType
)

from .fixtures import (
    make_minimal_factsheet,
    make_type_specification,
    make_physical_parameters,
    make_protocol_limits,
    make_protocol_features,
    make_agv_geometry,
    make_load_specification,
    make_wheel_definition,
    make_agv_action,
)


class TestFactsheetValidPayloads:
    """Test that Factsheet accepts valid payloads (Requirement 1)."""
    
    def test_minimal_valid_factsheet(self):
        """Test minimal valid Factsheet."""
        payload = make_minimal_factsheet()
        
        factsheet = Factsheet(**payload)
        
        assert factsheet.headerId == 1
        assert factsheet.typeSpecification.seriesName == "TestSeries"
        assert factsheet.typeSpecification.agvKinematic == AgvKinematic.DIFF
        assert factsheet.physicalParameters.speedMax == 2.0
        assert factsheet.protocolLimits is not None
        assert factsheet.protocolFeatures is not None
        assert factsheet.agvGeometry is not None
        assert factsheet.loadSpecification is not None
    
    def test_factsheet_with_all_optional_fields(self):
        """Test Factsheet with all optional fields populated."""
        payload = make_minimal_factsheet(
            vehicleConfig={
                "versions": [
                    {"key": "firmwareVersion", "value": "1.2.3"}
                ],
                "network": {
                    "localIpAddress": "192.168.1.100",
                    "netmask": "255.255.255.0"
                }
            }
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.vehicleConfig is not None
        assert len(factsheet.vehicleConfig.versions) == 1


class TestFactsheetMissingFields:
    """Test that Factsheet rejects missing required fields (Requirement 2)."""
    
    @pytest.mark.parametrize("field", [
        "typeSpecification", "physicalParameters", "protocolLimits",
        "protocolFeatures", "agvGeometry", "loadSpecification"
    ])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_minimal_factsheet()
        del payload[field]
        
        with pytest.raises(ValidationError):
            Factsheet(**payload)
    
    def test_type_specification_missing_required_fields(self):
        """Test that typeSpecification with missing required fields is rejected."""
        payload = make_minimal_factsheet(
            typeSpecification={
                "seriesName": "Test",
                # Missing: agvKinematic, agvClass, maxLoadMass, etc.
            }
        )
        
        with pytest.raises(ValidationError):
            Factsheet(**payload)


class TestFactsheetInvalidTypes:
    """Test that Factsheet rejects invalid field types (Requirement 3)."""
    
    def test_invalid_type_specification_field(self):
        """Test that invalid types in TypeSpecification are rejected."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(maxLoadMass=-100.0)
        )
        
        with pytest.raises(ValidationError):
            Factsheet(**payload)
    
    def test_invalid_physical_parameters(self):
        """Test that invalid PhysicalParameters are rejected."""
        payload = make_minimal_factsheet()
        payload["physicalParameters"]["speedMax"] = "not_a_number"
        
        with pytest.raises(ValidationError):
            Factsheet(**payload)


class TestFactsheetOptionalFields:
    """Test that Factsheet handles optional fields correctly (Requirement 4)."""
    
    def test_vehicle_config_is_optional(self):
        """Test that vehicleConfig is optional."""
        # Without vehicleConfig
        payload = make_minimal_factsheet()
        factsheet = Factsheet(**payload)
        assert factsheet.vehicleConfig is None
        
        # With vehicleConfig
        payload = make_minimal_factsheet(
            vehicleConfig={"versions": []}
        )
        factsheet = Factsheet(**payload)
        assert factsheet.vehicleConfig is not None
    
    def test_optional_fields_in_type_specification(self):
        """Test optional fields in TypeSpecification."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                seriesDescription="Optional description"
            )
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.seriesDescription == "Optional description"
    
    def test_optional_fields_in_physical_parameters(self):
        """Test optional fields in PhysicalParameters."""
        payload = make_minimal_factsheet()
        factsheet = Factsheet(**payload)
        
        # heightMin is optional
        assert factsheet.physicalParameters.heightMin is None


class TestFactsheetNestedValidation:
    """Test nested object and array validation (Requirement 5)."""
    
    def test_deeply_nested_type_specification(self):
        """Test TypeSpecification validation."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                agvKinematic="OMNI",
                agvClass="CARRIER",
                localizationTypes=["NATURAL", "REFLECTOR"],
                navigationTypes=["AUTONOMOUS"]
            )
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.agvKinematic == AgvKinematic.OMNI
        assert len(factsheet.typeSpecification.localizationTypes) == 2
    
    def test_protocol_limits_nesting(self):
        """Test ProtocolLimits with nested objects."""
        payload = make_minimal_factsheet(
            protocolLimits={
                "maxStringLens": {
                    "msgLen": 10000,
                    "idLen": 255
                },
                "maxArrayLens": {
                    "order.nodes": 100,
                    "order.edges": 100
                },
                "timing": {
                    "minOrderInterval": 1.0,
                    "minStateInterval": 0.5,
                    "defaultStateInterval": 1.0
                }
            }
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.protocolLimits.timing.minOrderInterval == 1.0
    
    def test_agv_geometry_with_wheels(self):
        """Test AgvGeometry with wheelDefinitions."""
        payload = make_minimal_factsheet(
            agvGeometry={
                "wheelDefinitions": [
                    make_wheel_definition(
                        type="DRIVE",
                        isActiveDriven=True,
                        isActiveSteered=False
                    )
                ]
            }
        )
        
        factsheet = Factsheet(**payload)
        assert len(factsheet.agvGeometry.wheelDefinitions) == 1
        assert factsheet.agvGeometry.wheelDefinitions[0].type == WheelType.DRIVE
    
    def test_protocol_features_with_actions(self):
        """Test ProtocolFeatures with agvActions array."""
        payload = make_minimal_factsheet(
            protocolFeatures={
                "optionalParameters": [],
                "agvActions": [
                    make_agv_action(
                        actionType="pick",
                        actionScopes=["NODE"],
                        actionDescription="Pick up load"
                    )
                ]
            }
        )
        
        factsheet = Factsheet(**payload)
        assert len(factsheet.protocolFeatures.agvActions) == 1
        assert factsheet.protocolFeatures.agvActions[0].actionType == "pick"


class TestFactsheetEnumValidation:
    """Test enum value enforcement (Requirement 6)."""
    
    @pytest.mark.parametrize("kinematic", ["DIFF", "OMNI", "THREEWHEEL"])
    def test_valid_agv_kinematics(self, kinematic):
        """Test that all valid AgvKinematic values are accepted."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(agvKinematic=kinematic)
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.agvKinematic.value == kinematic
    
    @pytest.mark.parametrize("agv_class", [
        "FORKLIFT", "CONVEYOR", "TUGGER", "CARRIER"
    ])
    def test_valid_agv_classes(self, agv_class):
        """Test that all valid AgvClass values are accepted."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(agvClass=agv_class)
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.agvClass.value == agv_class
    
    @pytest.mark.parametrize("loc_type", [
        "NATURAL", "REFLECTOR", "RFID", "DMC", "SPOT", "GRID"
    ])
    def test_valid_localization_types(self, loc_type):
        """Test that all valid LocalizationType values are accepted."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                localizationTypes=[loc_type]
            )
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.localizationTypes[0].value == loc_type
    
    @pytest.mark.parametrize("nav_type", [
        "PHYSICAL_LINE_GUIDED", "VIRTUAL_LINE_GUIDED", "AUTONOMOUS"
    ])
    def test_valid_navigation_types(self, nav_type):
        """Test that all valid NavigationType values are accepted."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                navigationTypes=[nav_type]
            )
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.navigationTypes[0].value == nav_type


class TestFactsheetSerialization:
    """Test JSON round-trip serialization (Requirement 7)."""
    
    def test_model_dump_json_round_trip(self):
        """Test serialization preserves all nested data."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                seriesName="TestBot3000",
                maxLoadMass=500.0
            )
        )
        
        original = Factsheet(**payload)
        json_str = original.model_dump_json()
        reconstructed = Factsheet.model_validate_json(json_str)
        
        assert reconstructed.typeSpecification.seriesName == "TestBot3000"
        assert reconstructed.typeSpecification.maxLoadMass == 500.0
    
    def test_complex_nested_serialization(self):
        """Test that deeply nested structures survive round-trip."""
        payload = make_minimal_factsheet(
            agvGeometry={
                "wheelDefinitions": [
                    make_wheel_definition()
                ],
                "envelopes2d": [
                    {
                        "set": "default",
                        "polygonPoints": [
                            {"x": 0.0, "y": 0.0},
                            {"x": 1.0, "y": 0.0},
                            {"x": 1.0, "y": 1.0}
                        ]
                    }
                ]
            }
        )
        
        original = Factsheet(**payload)
        reconstructed = Factsheet.model_validate(original.model_dump())
        
        assert len(reconstructed.agvGeometry.wheelDefinitions) == 1
        assert len(reconstructed.agvGeometry.envelopes2d) == 1


class TestFactsheetDataIntegrity:
    """Test data integrity preservation (Requirement 8)."""
    
    def test_float_precision_in_physical_parameters(self):
        """Test that float precision is maintained."""
        payload = make_minimal_factsheet(
            physicalParameters=make_physical_parameters(
                speedMin=0.123456,
                speedMax=2.987654,
                accelerationMax=1.234567
            )
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.physicalParameters.speedMin == 0.123456
        assert factsheet.physicalParameters.speedMax == 2.987654
    
    def test_array_order_preserved(self):
        """Test that array order is preserved."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                localizationTypes=["NATURAL", "REFLECTOR", "GRID"]
            )
        )
        
        factsheet = Factsheet(**payload)
        assert factsheet.typeSpecification.localizationTypes[0] == LocalizationType.NATURAL
        assert factsheet.typeSpecification.localizationTypes[1] == LocalizationType.REFLECTOR
        assert factsheet.typeSpecification.localizationTypes[2] == LocalizationType.GRID


class TestFactsheetErrorMessages:
    """Test clear error message generation (Requirement 9)."""
    
    def test_missing_nested_field_error(self):
        """Test that missing nested fields produce clear errors."""
        payload = make_minimal_factsheet()
        del payload["typeSpecification"]["agvKinematic"]
        
        with pytest.raises(ValidationError) as exc_info:
            Factsheet(**payload)
        
        error_str = str(exc_info.value)
        assert "agvKinematic" in error_str or "kinematic" in error_str.lower()
    
    def test_invalid_enum_in_nested_object(self):
        """Test that invalid enums in nested objects produce clear errors."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(agvKinematic="INVALID")
        )
        
        with pytest.raises(ValidationError) as exc_info:
            Factsheet(**payload)
        
        error_str = str(exc_info.value)
        assert "agvKinematic" in error_str or "kinematic" in error_str.lower()


class TestFactsheetEdgeCases:
    """Additional edge case tests."""
    
    def test_empty_optional_arrays(self):
        """Test that empty arrays in optional fields are accepted."""
        payload = make_minimal_factsheet(
            protocolFeatures={
                "optionalParameters": [],
                "agvActions": []
            },
            agvGeometry={
                "wheelDefinitions": [],
                "envelopes2d": [],
                "envelopes3d": []
            },
            loadSpecification={
                "loadPositions": [],
                "loadSets": []
            }
        )
        
        factsheet = Factsheet(**payload)
        assert len(factsheet.protocolFeatures.agvActions) == 0
        assert len(factsheet.agvGeometry.wheelDefinitions) == 0
    
    def test_maximum_complexity_factsheet(self):
        """Test Factsheet with maximum complexity and all fields."""
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(
                seriesDescription="Full description",
                localizationTypes=["NATURAL", "REFLECTOR"],
                navigationTypes=["AUTONOMOUS", "VIRTUAL_LINE_GUIDED"]
            ),
            physicalParameters=make_physical_parameters(
                heightMin=0.5
            ),
            vehicleConfig={
                "versions": [
                    {"key": "firmware", "value": "1.0"},
                    {"key": "software", "value": "2.0"}
                ],
                "network": {
                    "dnsServers": ["8.8.8.8"],
                    "localIpAddress": "192.168.1.100",
                    "ntpServers": ["pool.ntp.org"],
                    "netmask": "255.255.255.0",
                    "defaultGateway": "192.168.1.1"
                }
            },
            protocolFeatures={
                "optionalParameters": [
                    {
                        "parameter": "order.nodes.nodePosition.theta",
                        "support": "REQUIRED"
                    }
                ],
                "agvActions": [
                    make_agv_action(
                        actionType="pick",
                        actionScopes=["NODE", "INSTANT"],
                        actionParameters=[
                            {
                                "key": "loadId",
                                "valueDataType": "STRING",
                                "isOptional": False
                            }
                        ]
                    )
                ]
            }
        )
        
        factsheet = Factsheet(**payload)
        assert len(factsheet.typeSpecification.localizationTypes) == 2
        assert len(factsheet.vehicleConfig.versions) == 2
        assert len(factsheet.protocolFeatures.agvActions) == 1
    
    def test_constraint_validation_in_nested_objects(self):
        """Test that constraints in nested objects are enforced."""
        # maxLoadMass must be >= 0.0
        payload = make_minimal_factsheet(
            typeSpecification=make_type_specification(maxLoadMass=-1.0)
        )
        
        with pytest.raises(ValidationError):
            Factsheet(**payload)

