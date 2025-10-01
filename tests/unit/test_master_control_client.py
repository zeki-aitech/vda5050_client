# tests/unit/test_master_control_client.py

import pytest
from unittest.mock import AsyncMock, Mock
from vda5050.clients.master_control import MasterControlClient
from vda5050.core.mqtt_abstraction import MQTTAbstraction
from vda5050.core.topic_manager import TopicManager
from vda5050.models.state import State
from vda5050.models.order import Order
from vda5050.models.instant_action import InstantActions

@pytest.fixture
def mock_mqtt(monkeypatch):
    """Mock MQTTAbstraction so subscribe and publish calls are captured."""
    mqtt = Mock(spec=MQTTAbstraction)
    mqtt.subscribe = AsyncMock(return_value=None)
    mqtt.publish = AsyncMock(return_value=True)
    monkeypatch.setattr(MQTTAbstraction, "__init__", lambda self, **kwargs: None)
    monkeypatch.setattr(MQTTAbstraction, "connect", AsyncMock(return_value=True))
    monkeypatch.setattr(MQTTAbstraction, "disconnect", AsyncMock(return_value=None))
    monkeypatch.setattr(MQTTAbstraction, "subscribe", mqtt.subscribe)
    monkeypatch.setattr(MQTTAbstraction, "publish", mqtt.publish)
    return mqtt

@pytest.fixture
def client(monkeypatch, mock_mqtt):
    """Instantiate MasterControlClient with mocked MQTT and TopicManager."""
    # Stub out MQTTAbstraction.__init__ so it doesn't overwrite mqtt/topic_manager
    monkeypatch.setattr(MQTTAbstraction, "__init__", lambda self, *args, **kwargs: None)

    # Create the client instance
    mc = MasterControlClient("broker", "TestMan", "Test001")
    # Inject the mocked MQTTAbstraction instance
    mc.mqtt = mock_mqtt
    # Create and assign a real TopicManager instance
    mc.topic_manager = TopicManager("uagv", "2.1.0", "TestMan", "Test001")
    # Mark as connected for testing
    mc._connected = True
    return mc

def test_setup_subscriptions(client, mock_mqtt):
    """
    _setup_subscriptions should be a no-op since subscriptions are handled by base class.
    """
    # Call setup - should be a no-op now
    import asyncio; asyncio.run(client._setup_subscriptions())
    
    # No direct MQTT subscriptions should be made in _setup_subscriptions
    # The actual subscriptions are handled by register_handler calls in __init__
    # and set up during connection via _setup_registered_handlers

def test_handle_state_invokes_callbacks(client):
    """
    _handle_state parses topic, builds State, and calls registered callbacks.
    """
    # Prepare a fake State JSON with required fields
    payload = State(
        headerId=1,
        timestamp="2025-10-01T12:00:00Z",
        version="2.1.0",
        manufacturer="TestMan",
        serialNumber="Test001",
        orderId="o1",
        orderUpdateId=1,
        lastNodeId="n1",
        lastNodeSequenceId=1,
        driving=True,
        operatingMode="AUTOMATIC",
        nodeStates=[],
        edgeStates=[],
        actionStates=[],
        batteryState={"batteryCharge": 100.0, "charging": False},
        errors=[],
        safetyState={"eStop": "NONE", "fieldViolation": False},
        position={"x": 1, "y": 2, "theta": 0, "mapId": "test_map"},
        info={}
    ).model_dump_json()
    # Spy callback
    called = []
    client.on_state_update(lambda serial, st: called.append((serial, st)))

    # Simulate handling
    topic = "uagv/v2/TestMan/Test001/state"
    import asyncio; asyncio.run(client._handle_state(topic, payload))

    assert called and called[0][0] == "Test001"
    assert isinstance(called[0][1], State)

def test_handle_state_bad_payload_logs_error(client, caplog):
    """
    Invalid JSON payload should log an error and not raise.
    """
    caplog.set_level("ERROR")
    client.on_state_update(lambda *_: (_ for _ in ()).throw(AssertionError()))

    # Bad JSON
    import asyncio; asyncio.run(client._handle_state("uagv/v2/TestMan/Test001/state", "notjson"))
    assert "Failed to parse State payload" in caplog.text

def test_handle_connection_invokes_callbacks(client):
    """
    _handle_connection parses topic and invokes connection-change callbacks.
    """
    called = []
    client.on_connection_change(lambda serial, st: called.append((serial, st)))

    topic = "uagv/v2/TestMan/Test001/connection"
    # Use proper JSON payload for Connection message
    payload = '{"headerId": 1, "timestamp": "2023-01-01T00:00:00Z", "version": "2.1.0", "manufacturer": "TestMan", "serialNumber": "Test001", "connectionState": "ONLINE"}'
    import asyncio; asyncio.run(client._handle_connection(topic, payload))

    assert called == [("Test001", "ONLINE")]

def test_send_order_calls_publish(client, mock_mqtt):
    """
    send_order should call _publish_message via MQTT.publish and return True.
    """
    order = Order(
        orderId="o1",
        headerId=1,
        timestamp="2025-10-01T12:00:00Z",
        version="2.1.0",
        manufacturer="TestMan",
        serialNumber="Test001",
        orderUpdateId=1,
        nodes=[],
        edges=[]
    )
    import asyncio; result = asyncio.run(client.send_order("TestMan", "Test001", order))
    assert result is True
    # Verify that publish was called with correct topic
    topic = client.topic_manager.get_target_topic("order", "TestMan", "Test001")
    # Get the actual call arguments to verify the correct topic and payload
    call_args = mock_mqtt.publish.await_args
    assert call_args[0][0] == topic  # Check topic
    # Check that the payload contains the expected order data
    payload = call_args[0][1]
    assert "orderId" in payload
    assert "TestMan" in payload
    assert "Test001" in payload

def test_send_instant_action_calls_publish(client, mock_mqtt):
    """
    send_instant_action should call MQTT.publish and return True.
    """
    action = InstantActions(
        headerId=1,
        timestamp="2025-10-01T12:00:00Z",
        version="2.1.0",
        manufacturer="TestMan",
        serialNumber="Test001",
        actions=[]
    )
    import asyncio; result = asyncio.run(client.send_instant_action("TestMan", "Test001", action))
    assert result is True
    topic = client.topic_manager.get_target_topic("instantActions", "TestMan", "Test001")
    # Get the actual call arguments to verify the correct topic and payload
    call_args = mock_mqtt.publish.await_args
    assert call_args[0][0] == topic  # Check topic
    # Check that the payload contains the expected action data
    payload = call_args[0][1]
    assert "actions" in payload
    assert "TestMan" in payload
    assert "Test001" in payload
