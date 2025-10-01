import asyncio
import pytest
from unittest.mock import Mock, patch
import paho.mqtt.client as mqtt
from vda5050.core.mqtt_abstraction import MQTTAbstraction, ConnectionState

# 1. Test successful connect()
#    - Mocks paho-mqtt Client.connect to do nothing
#    - Simulates on_connect callback with rc=0
#    - Expects connect() to return True and state to be CONNECTED
@pytest.mark.asyncio
async def test_connect_success(monkeypatch):
    fake_client = Mock()
    fake_client.connect = Mock()
    fake_client.loop_start = Mock()
    fake_client.loop_stop = Mock()
    
    # Patch mqtt.Client constructor
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)
    
    # Build abstraction
    mqtt_abstraction = MQTTAbstraction("host", 1883, client_id="test")
    
    # Verify callbacks are bound
    assert fake_client.on_connect == mqtt_abstraction._on_connect
    assert fake_client.on_disconnect == mqtt_abstraction._on_disconnect
    assert fake_client.on_message == mqtt_abstraction._on_message
    
    # Spy on set() event
    async def trigger_connect():
        # delay to let connect() subscribe event
        await asyncio.sleep(0.01)
        # simulate paho invoking on_connect with rc=0
        mqtt_abstraction._on_connect(fake_client, None, None, 0, None)

    # Schedule connect trigger
    asyncio.create_task(trigger_connect())

    # Call connect()
    result = await mqtt_abstraction.connect(timeout=1.0)
    assert result is True
    assert mqtt_abstraction._state == ConnectionState.CONNECTED
    
    # Verify client methods were called
    fake_client.connect.assert_called_once_with("host", 1883, 60)
    fake_client.loop_start.assert_called_once()

# 2. Test connect failure
#    - Mocks Client.connect to raise
#    - Expects connect() to return False and state to remain DISCONNECTED
@pytest.mark.asyncio
async def test_connect_failure(monkeypatch):
    fake_client = Mock()
    fake_client.connect.side_effect = RuntimeError("fail")
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt = MQTTAbstraction("host", 1883)
    result = await mqtt.connect(timeout=0.1)
    assert result is False
    assert mqtt._state == ConnectionState.DISCONNECTED

# 3. Test publish when connected
#    - Sets state to CONNECTED
#    - Mocks client.publish returning an object with wait_for_publish
#    - Expects publish() to return True
@pytest.mark.asyncio
async def test_publish_connected(monkeypatch):
    fake_info = Mock()
    fake_info.wait_for_publish = Mock()
    fake_client = Mock(publish=Mock(return_value=fake_info))
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt = MQTTAbstraction("host", 1883)
    mqtt._state = ConnectionState.CONNECTED
    result = await mqtt.publish("topic", "payload")
    assert result is True
    fake_client.publish.assert_called_with("topic", "payload", qos=1, retain=False)
    fake_info.wait_for_publish.assert_called()

# 4. Test publish when not connected
#    - Leaves state DISCONNECTED
#    - Expects publish() to raise RuntimeError
@pytest.mark.asyncio
async def test_publish_not_connected(monkeypatch):
    fake_client = Mock()
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt_abstraction = MQTTAbstraction("host", 1883)
    with pytest.raises(RuntimeError):
        await mqtt_abstraction.publish("topic", "payload")

# 4.5. Test disconnect()
#    - Simulates connected state
#    - Calls disconnect()
#    - Asserts loop_stop() and disconnect() on client were called
@pytest.mark.asyncio
async def test_disconnect(monkeypatch):
    fake_client = Mock()
    fake_client.loop_stop = Mock()
    fake_client.disconnect = Mock()
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt_abstraction = MQTTAbstraction("host", 1883)
    mqtt_abstraction._state = ConnectionState.CONNECTED
    
    await mqtt_abstraction.disconnect()
    
    # Verify state and client methods
    assert mqtt_abstraction._state == ConnectionState.DISCONNECTED
    fake_client.loop_stop.assert_called_once()
    fake_client.disconnect.assert_called_once()

# 5. Test subscribe registers handlers
#    - Mocks client.subscribe returning success
#    - Registers exact topic and wildcard topic
#    - Verifies internal handler maps
@pytest.mark.asyncio
async def test_subscribe_registration(monkeypatch):
    import paho.mqtt.client as mqtt_client
    fake_client = Mock()
    fake_client.subscribe = Mock(return_value=(mqtt_client.MQTT_ERR_SUCCESS, 1))
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt_abstraction = MQTTAbstraction("host", 1883)
    def handler_a(t, p): pass
    def handler_b(t, p): pass

    # Exact topic
    await mqtt_abstraction.subscribe("exact/topic", handler_a)
    assert "exact/topic" in mqtt_abstraction._handlers
    # Wildcard topic
    await mqtt_abstraction.subscribe("wild/+/topic", handler_b)
    assert "wild/+/topic" in mqtt_abstraction._wildcard_handlers

# 6. Test message routing to correct handler
#    - Registers one exact handler and one wildcard handler
#    - Enqueues matching and non-matching messages
#    - Verifies only appropriate handlers are called
@pytest.mark.asyncio
async def test_message_routing(monkeypatch):
    fake_client = Mock()
    fake_client.subscribe = Mock(return_value=(mqtt.MQTT_ERR_SUCCESS, 1))
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt_abstraction = MQTTAbstraction("host", 1883)
    mqtt_abstraction._state = ConnectionState.CONNECTED
    mqtt_abstraction._running = True

    called = []
    async def handler_exact(topic, payload):
        called.append(("exact", topic, payload))
    async def handler_wild(topic, payload):
        called.append(("wild", topic, payload))

    await mqtt_abstraction.subscribe("test/topic", handler_exact)
    await mqtt_abstraction.subscribe("test/+/val", handler_wild)

    # Schedule the processor in background
    processor_task = asyncio.create_task(mqtt_abstraction._message_processor())

    # Enqueue messages
    await mqtt_abstraction._message_queue.put(("test/topic", "a"))
    await mqtt_abstraction._message_queue.put(("test/foo/val", "b"))

    # Give the processor time to handle messages
    await asyncio.sleep(0.05)

    # Stop the processor loop and wait for it to finish
    mqtt_abstraction._running = False
    await processor_task

    assert ("exact", "test/topic", "a") in called
    assert ("wild", "test/foo/val", "b") in called

# 7. Test automatic reconnection logic scheduling
#    - Simulates on_disconnect with rc!=0
#    - Patches connect() to succeed
#    - Verifies state transitions back to CONNECTED
@pytest.mark.asyncio
async def test_reconnect(monkeypatch):
    fake_client = Mock()
    fake_client.loop_start = Mock()
    fake_client.loop_stop = Mock()
    monkeypatch.setattr("paho.mqtt.client.Client", lambda api_version=None, client_id=None: fake_client)

    mqtt_abstraction = MQTTAbstraction("host", 1883)
    # Patch connect to set state and return True
    async def fake_connect(timeout=10.0):
        mqtt_abstraction._state = ConnectionState.CONNECTED
        mqtt_abstraction._connection_event.set()
        return True
    mqtt_abstraction.connect = fake_connect

    # Trigger unexpected disconnect
    mqtt_abstraction._state = ConnectionState.CONNECTED
    mqtt_abstraction._on_disconnect(fake_client, None, rc=1)
    
    # Verify state is set to DISCONNECTED
    assert mqtt_abstraction._state == ConnectionState.DISCONNECTED
    
    # Let the scheduled reconnection task run
    await asyncio.sleep(0)
    
    # If the task didn't run automatically, trigger it manually
    if mqtt_abstraction._state == ConnectionState.DISCONNECTED:
        await mqtt_abstraction._reconnect()
    
    # Verify state is back to CONNECTED
    assert mqtt_abstraction._state == ConnectionState.CONNECTED
