"""
Unit tests for the VDA5050 Order message model.

The Order message contains a graph structure of nodes and edges with actions,
trajectories, and various navigation parameters.

Tests verify all 9 Pydantic model validation requirements.
"""

import pytest
from pydantic import ValidationError

from vda5050.models.order import Order, Node, Edge
from vda5050.models.base import BlockingType

from .fixtures import (
    make_minimal_order,
    make_node,
    make_edge,
    make_node_position,
    make_trajectory,
    make_action,
)


class TestOrderValidPayloads:
    """Test that Order accepts valid payloads (Requirement 1)."""
    
    def test_minimal_valid_order(self):
        """Test minimal valid Order with one node and no edges."""
        payload = make_minimal_order()
        
        order = Order(**payload)
        
        assert order.orderId == "order_001"
        assert order.orderUpdateId == 0
        assert len(order.nodes) == 1
        assert len(order.edges) == 0
    
    def test_order_with_multiple_nodes_and_edges(self):
        """Test Order with multiple nodes and edges."""
        payload = make_minimal_order(
            nodes=[
                make_node(nodeId="n1", sequenceId=0),
                make_node(nodeId="n2", sequenceId=2),
                make_node(nodeId="n3", sequenceId=4),
            ],
            edges=[
                make_edge(edgeId="e1", sequenceId=1, startNodeId="n1", endNodeId="n2"),
                make_edge(edgeId="e2", sequenceId=3, startNodeId="n2", endNodeId="n3"),
            ]
        )
        
        order = Order(**payload)
        
        assert len(order.nodes) == 3
        assert len(order.edges) == 2
        assert order.edges[0].startNodeId == "n1"
    
    def test_order_with_node_positions(self):
        """Test Order with nodePosition in nodes."""
        payload = make_minimal_order(
            nodes=[
                make_node(
                    nodeId="n1",
                    sequenceId=0,
                    nodePosition=make_node_position(x=10.0, y=20.0, mapId="map1")
                )
            ]
        )
        
        order = Order(**payload)
        assert order.nodes[0].nodePosition.x == 10.0
    
    def test_order_with_trajectories(self):
        """Test Order with trajectory in edges."""
        payload = make_minimal_order(
            nodes=[
                make_node(nodeId="n1", sequenceId=0),
                make_node(nodeId="n2", sequenceId=2),
            ],
            edges=[
                make_edge(
                    edgeId="e1",
                    sequenceId=1,
                    startNodeId="n1",
                    endNodeId="n2",
                    trajectory=make_trajectory()
                )
            ]
        )
        
        order = Order(**payload)
        assert order.edges[0].trajectory is not None
        assert order.edges[0].trajectory.degree == 1


class TestOrderMissingFields:
    """Test that Order rejects missing required fields (Requirement 2)."""
    
    @pytest.mark.parametrize("field", [
        "headerId", "timestamp", "version", "manufacturer", "serialNumber",
        "orderId", "orderUpdateId", "nodes", "edges"
    ])
    def test_missing_required_field(self, field):
        """Test that missing required fields raise ValidationError."""
        payload = make_minimal_order()
        del payload[field]
        
        with pytest.raises(ValidationError):
            Order(**payload)
    
    def test_node_missing_required_fields(self):
        """Test that nodes with missing required fields are rejected."""
        payload = make_minimal_order(
            nodes=[{"nodeId": "n1"}]  # Missing sequenceId, released, actions
        )
        
        with pytest.raises(ValidationError):
            Order(**payload)


class TestOrderInvalidTypes:
    """Test that Order rejects invalid field types (Requirement 3)."""
    
    @pytest.mark.parametrize("field,invalid_value", [
        ("orderId", 123),
        ("orderUpdateId", "not_int"),
        ("orderUpdateId", -1),  # Must be >= 0
        ("nodes", "not_list"),
        ("edges", "not_list"),
    ])
    def test_invalid_field_types(self, field, invalid_value):
        """Test that invalid types are rejected."""
        payload = make_minimal_order()
        payload[field] = invalid_value
        
        with pytest.raises(ValidationError):
            Order(**payload)
    
    def test_invalid_node_sequence_id(self):
        """Test that negative sequenceId is rejected."""
        payload = make_minimal_order(
            nodes=[make_node(sequenceId=-1)]
        )
        
        with pytest.raises(ValidationError):
            Order(**payload)


class TestOrderOptionalFields:
    """Test that Order handles optional fields correctly (Requirement 4)."""
    
    def test_zone_set_id_is_optional(self):
        """Test that zoneSetId is optional."""
        # Without zoneSetId
        payload = make_minimal_order()
        order = Order(**payload)
        assert order.zoneSetId is None
        
        # With zoneSetId
        payload = make_minimal_order(zoneSetId="zone_1")
        order = Order(**payload)
        assert order.zoneSetId == "zone_1"
    
    def test_node_position_is_optional(self):
        """Test that nodePosition in nodes is optional."""
        payload = make_minimal_order(
            nodes=[make_node()]
        )
        
        order = Order(**payload)
        assert order.nodes[0].nodePosition is None
    
    def test_node_description_is_optional(self):
        """Test that nodeDescription is optional."""
        payload = make_minimal_order(
            nodes=[make_node(nodeDescription="Test node")]
        )
        
        order = Order(**payload)
        assert order.nodes[0].nodeDescription == "Test node"


class TestOrderNestedValidation:
    """Test nested object and array validation (Requirement 5)."""
    
    def test_nested_nodes_validation(self):
        """Test that Node objects are validated."""
        payload = make_minimal_order(
            nodes=[make_node(nodeId="n1", sequenceId=0)]
        )
        
        order = Order(**payload)
        assert isinstance(order.nodes[0], Node)
    
    def test_nested_edges_validation(self):
        """Test that Edge objects are validated."""
        payload = make_minimal_order(
            nodes=[
                make_node(nodeId="n1", sequenceId=0),
                make_node(nodeId="n2", sequenceId=2),
            ],
            edges=[
                make_edge(sequenceId=1, startNodeId="n1", endNodeId="n2")
            ]
        )
        
        order = Order(**payload)
        assert isinstance(order.edges[0], Edge)
    
    def test_nested_actions_in_nodes(self):
        """Test that Action arrays in nodes are validated."""
        payload = make_minimal_order(
            nodes=[
                make_node(
                    actions=[
                        make_action(actionId="a1", blockingType="SOFT"),
                        make_action(actionId="a2", blockingType="HARD"),
                    ]
                )
            ]
        )
        
        order = Order(**payload)
        assert len(order.nodes[0].actions) == 2
        assert order.nodes[0].actions[0].blockingType == BlockingType.SOFT
    
    def test_trajectory_validation(self):
        """Test that Trajectory in edges is validated."""
        payload = make_minimal_order(
            nodes=[
                make_node(nodeId="n1", sequenceId=0),
                make_node(nodeId="n2", sequenceId=2),
            ],
            edges=[
                make_edge(
                    sequenceId=1,
                    startNodeId="n1",
                    endNodeId="n2",
                    trajectory=make_trajectory(degree=2)
                )
            ]
        )
        
        order = Order(**payload)
        assert order.edges[0].trajectory.degree == 2


class TestOrderEnumValidation:
    """Test enum value enforcement (Requirement 6)."""
    
    @pytest.mark.parametrize("blocking_type", ["NONE", "SOFT", "HARD"])
    def test_valid_blocking_types_in_actions(self, blocking_type):
        """Test that valid BlockingType values are accepted in node actions."""
        payload = make_minimal_order(
            nodes=[
                make_node(
                    actions=[make_action(blockingType=blocking_type)]
                )
            ]
        )
        
        order = Order(**payload)
        assert order.nodes[0].actions[0].blockingType.value == blocking_type


class TestOrderSerialization:
    """Test JSON round-trip serialization (Requirement 7)."""
    
    def test_model_dump_json_round_trip(self):
        """Test serialization preserves all data."""
        payload = make_minimal_order(
            orderId="order_123",
            orderUpdateId=5,
            nodes=[
                make_node(nodeId="n1", sequenceId=0),
                make_node(nodeId="n2", sequenceId=2),
            ],
            edges=[
                make_edge(sequenceId=1, startNodeId="n1", endNodeId="n2")
            ]
        )
        
        original = Order(**payload)
        json_str = original.model_dump_json()
        reconstructed = Order.model_validate_json(json_str)
        
        assert reconstructed.orderId == original.orderId
        assert len(reconstructed.nodes) == 2
        assert reconstructed.edges[0].startNodeId == "n1"


class TestOrderDataIntegrity:
    """Test data integrity preservation (Requirement 8)."""
    
    def test_node_order_preserved(self):
        """Test that node array order is preserved."""
        payload = make_minimal_order(
            nodes=[
                make_node(nodeId="first", sequenceId=0),
                make_node(nodeId="second", sequenceId=2),
                make_node(nodeId="third", sequenceId=4),
            ]
        )
        
        order = Order(**payload)
        
        assert order.nodes[0].nodeId == "first"
        assert order.nodes[1].nodeId == "second"
        assert order.nodes[2].nodeId == "third"
    
    def test_float_precision_in_node_positions(self):
        """Test that float precision is maintained in node positions."""
        payload = make_minimal_order(
            nodes=[
                make_node(
                    nodePosition=make_node_position(
                        x=123.456789,
                        y=987.654321,
                        theta=3.14159265
                    )
                )
            ]
        )
        
        order = Order(**payload)
        assert order.nodes[0].nodePosition.x == 123.456789


class TestOrderErrorMessages:
    """Test clear error message generation (Requirement 9)."""
    
    def test_missing_field_error_clarity(self):
        """Test that missing fields produce clear errors."""
        payload = make_minimal_order()
        del payload["orderId"]
        
        with pytest.raises(ValidationError) as exc_info:
            Order(**payload)
        
        error_str = str(exc_info.value)
        assert "orderId" in error_str or "order_id" in error_str.lower()


class TestOrderEdgeCases:
    """Additional edge case tests."""
    
    def test_empty_nodes_array(self):
        """Test behavior with empty nodes array."""
        payload = make_minimal_order(nodes=[], edges=[])
        
        # Model may allow empty array - documenting behavior
        order = Order(**payload)
        assert len(order.nodes) == 0
    
    def test_large_sequence_ids(self):
        """Test that large sequence IDs are handled."""
        payload = make_minimal_order(
            nodes=[make_node(sequenceId=999999)]
        )
        
        order = Order(**payload)
        assert order.nodes[0].sequenceId == 999999
    
    def test_complex_nested_structure(self):
        """Test complex nested structure with all optional fields."""
        payload = make_minimal_order(
            zoneSetId="zone_1",
            nodes=[
                make_node(
                    nodeId="complex_node",
                    sequenceId=0,
                    nodeDescription="Complex node with all fields",
                    nodePosition=make_node_position(
                        x=10.0,
                        y=20.0,
                        theta=1.57,
                        allowedDeviationXY=0.5,
                        allowedDeviationTheta=0.1,
                        mapId="map1",
                        mapDescription="Test map"
                    ),
                    actions=[
                        make_action(
                            actionId="a1",
                            actionType="pick",
                            blockingType="SOFT",
                            actionDescription="Pick action",
                            actionParameters=[
                                {"key": "loadId", "value": "LOAD_123"}
                            ]
                        )
                    ]
                )
            ]
        )
        
        order = Order(**payload)
        assert order.nodes[0].nodePosition.theta == 1.57
        assert len(order.nodes[0].actions) == 1

