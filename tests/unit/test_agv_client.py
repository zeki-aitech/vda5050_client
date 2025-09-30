# tests/unit/test_agv_client.py

import pytest
from unittest.mock import AsyncMock, Mock
from vda5050.clients.agv import AGVClient
from vda5050.core.mqtt_abstraction import MQTTAbstraction
from vda5050.core.topic_manager import TopicManager
from vda5050.models.factsheet import Factsheet
from vda5050.models.order import Order
from vda5050.models.instant_action import InstantActions
from vda5050.models.state import State
from vda5050.models.factsheet import (
    TypeSpecification, PhysicalParameters, ProtocolLimits, ProtocolFeatures,
    AgvGeometry, LoadSpecification, MaxStringLens, MaxArrayLens, Timing,
    AgvKinematic, AgvClass, LocalizationType, NavigationType, ActionScope,
    ValueDataType, ActionParameter, AgvAction, OptionalParameter, Support
)
from vda5050.models.order import Node, Edge, NodePosition
from vda5050.models.base import Action, VDA5050Message

@pytest.fixture
def minimal_factsheet_dict():
    """Create a minimal valid Factsheet data structure."""
    return {
        "headerId": 1,
        "timestamp": "2025-01-01T00:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "Test001",
        "typeSpecification": {
            "seriesName": "TestSeries",
            "agvKinematic": "DIFF",
            "agvClass": "CARRIER",
            "maxLoadMass": 100.0,
            "localizationTypes": ["NATURAL"],
            "navigationTypes": ["AUTONOMOUS"]
        },
        "physicalParameters": {
            "speedMin": 0.1,
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
                "minOrderInterval": 0.1,
                "minStateInterval": 0.1
            }
        },
        "protocolFeatures": {
            "optionalParameters": [],
            "agvActions": []
        },
        "agvGeometry": {},
        "loadSpecification": {}
    }

@pytest.fixture
def minimal_order_dict():
    """Create a minimal valid Order data structure."""
    return {
        "headerId": 1,
        "timestamp": "2025-01-01T00:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "Test001",
        "orderId": "o1",
        "orderUpdateId": 1,
        "nodes": [{
            "nodeId": "n1",
            "sequenceId": 1,
            "released": True,
            "actions": []
        }],
        "edges": []
    }

@pytest.fixture
def minimal_state_dict():
    """Create a minimal valid State data structure."""
    return {
        "headerId": 1,
        "timestamp": "2025-01-01T00:00:00Z",
        "version": "2.1.0",
        "manufacturer": "TestMan",
        "serialNumber": "Test001",
        "orderId": "",
        "orderUpdateId": 0,
        "lastNodeId": "",
        "lastNodeSequenceId": 0,
        "driving": False,
        "operatingMode": "AUTOMATIC",
        "nodeStates": [],
        "edgeStates": [],
        "actionStates": [],
        "batteryState": {
            "batteryCharge": 80.0,
            "charging": False
        },
        "errors": [],
        "safetyState": {
            "eStop": "NONE",
            "fieldViolation": False
        }
    }

@pytest.fixture
def factsheet(minimal_factsheet_dict):
    """Create a valid Factsheet instance."""
    return Factsheet(**minimal_factsheet_dict)

@pytest.fixture
def order(minimal_order_dict):
    """Create a valid Order instance."""
    return Order(**minimal_order_dict)

@pytest.fixture
def state(minimal_state_dict):
    """Create a valid State instance."""
    return State(**minimal_state_dict)

@pytest.fixture
def mock_mqtt(monkeypatch):
    """Mock MQTTAbstraction so subscribe and publish calls are captured."""
    mqtt = Mock(spec=MQTTAbstraction)
    mqtt.subscribe = AsyncMock(return_value=None)
    mqtt.publish = AsyncMock(return_value=True)
    monkeypatch.setattr(MQTTAbstraction, "__init__", lambda self, **kw: None)
    monkeypatch.setattr(MQTTAbstraction, "connect", AsyncMock(return_value=True))
    monkeypatch.setattr(MQTTAbstraction, "disconnect", AsyncMock(return_value=None))
    monkeypatch.setattr(MQTTAbstraction, "subscribe", mqtt.subscribe)
    monkeypatch.setattr(MQTTAbstraction, "publish", mqtt.publish)
    return mqtt

@pytest.fixture
def client(monkeypatch, mock_mqtt):
    """Instantiate AGVClient with mocked MQTT and real TopicManager."""
    monkeypatch.setattr(MQTTAbstraction, "__init__", lambda self, **kw: None)
    agv = AGVClient("broker", "TestMan", "Test001")
    agv.mqtt = mock_mqtt
    agv.topic_manager = TopicManager("uagv", "2.1.0", "TestMan", "Test001")
    agv._connected = True  # Mock the connection status
    return agv

def test_setup_subscriptions(client, mock_mqtt):
    """_setup_subscriptions should subscribe to this AGV's order and instantActions topics."""
    import asyncio; asyncio.run(client._setup_subscriptions())

    order_topic = "uagv/v2/TestMan/Test001/order"
    inst_topic  = "uagv/v2/TestMan/Test001/instantActions"

    mock_mqtt.subscribe.assert_any_await(order_topic, client._handle_order)
    mock_mqtt.subscribe.assert_any_await(inst_topic,  client._handle_instant_action)

def test_factsheet_sent_on_connect(client, mock_mqtt, factsheet):
    """_on_vda5050_connect should publish the stored Factsheet."""
    # store factsheet
    import asyncio; asyncio.run(client.send_factsheet(factsheet))

    # simulate connect hook
    import asyncio; asyncio.run(client._on_vda5050_connect())

    topic = "uagv/v2/TestMan/Test001/factsheet"
    mock_mqtt.publish.assert_awaited_with(topic, factsheet.to_mqtt_payload())

def test_handle_order_invokes_callbacks(client, order):
    """_handle_order should parse payload and invoke registered callbacks."""
    # prepare a valid Order
    payload = order.to_mqtt_payload()
    called = []
    client.on_order_received(lambda o: called.append(o))

    topic = "uagv/v2/TestMan/Test001/order"
    import asyncio; asyncio.run(client._handle_order(topic, payload))

    assert len(called) == 1
    assert isinstance(called[0], Order)
    assert called[0].orderId == "o1"

def test_handle_order_bad_payload_logs_error(client, caplog):
    """Invalid Order JSON should log an error and not invoke callbacks."""
    caplog.set_level("ERROR")
    called = []
    client.on_order_received(lambda o: called.append(o))

    import asyncio; asyncio.run(client._handle_order("uagv/v2/TestMan/Test001/order", "bad"))
    assert "Failed to parse Order payload" in caplog.text
    assert called == []

def test_send_methods_publish(client, mock_mqtt, factsheet, state):
    """send_factsheet, send_state, update_connection should call publish() correctly."""
    # Factsheet
    import asyncio
    res = asyncio.run(client.send_factsheet(factsheet))
    assert res is True
    mock_mqtt.publish.assert_awaited_with(
        "uagv/v2/TestMan/Test001/factsheet", factsheet.to_mqtt_payload()
    )

    # State
    res = asyncio.run(client.send_state(state))
    assert res is True
    mock_mqtt.publish.assert_awaited_with(
        "uagv/v2/TestMan/Test001/state", state.to_mqtt_payload()
    )

    # Connection
    res = asyncio.run(client.update_connection("DISCONNECTED"))
    assert res is True
    mock_mqtt.publish.assert_awaited_with(
        "uagv/v2/TestMan/Test001/connection", "DISCONNECTED"
    )

def test_send_methods_handle_failure(client, mock_mqtt, factsheet, state):
    """Methods should return False when publish() fails."""
    mock_mqtt.publish = AsyncMock(return_value=False)
    import asyncio
    assert asyncio.run(client.send_factsheet(factsheet)) is False
    assert asyncio.run(client.send_state(state)) is False
    assert asyncio.run(client.update_connection("OK")) is False
