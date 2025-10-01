# tests/integration/test_integration_smoke.py

import asyncio
import pytest
import logging
from vda5050.clients.agv import AGVClient
from vda5050.clients.master_control import MasterControlClient
from vda5050.models.factsheet import Factsheet
from vda5050.models.state import State
from vda5050.models.order import Order
from vda5050.models.instant_action import InstantActions
from vda5050.models.connection import ConnectionState

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("integration")

BROKER_URL = "localhost"
BROKER_PORT = 1883

@pytest.mark.asyncio
async def test_integration_smoke():
    """
    Integration smoke test verifying the complete VDA5050 message flow
    across all layers: schema validation, Pydantic parsing, MQTT transport, and callback invocation.
    
    Tests all six core message types:
    1. Connection ONLINE
    2. Factsheet
    3. State
    4. Order
    5. InstantActions
    6. Connection OFFLINE
    """
    
    # Events to signal receipt of each message with proper validation
    connection_online_received = asyncio.Event()
    factsheet_received = asyncio.Event()
    state_received = asyncio.Event()
    order_received = asyncio.Event()
    instant_action_received = asyncio.Event()
    connection_offline_received = asyncio.Event()
    
    # Store received messages for validation
    received_factsheet = None
    received_state = None
    received_order = None
    received_instant_action = None
    
    # Test data
    manufacturer = "TestMan"
    serial_number = "AGV001"
    
    # 1. Start AGVClient
    agv = AGVClient(
        broker_url=BROKER_URL,
        broker_port=BROKER_PORT,
        manufacturer=manufacturer,
        serial_number=serial_number,
        validate_messages=True
    )
    
    # Register AGV callbacks with proper signatures
    def on_order_received(order: Order):
        nonlocal received_order
        received_order = order
        order_received.set()
        LOGGER.info(f"AGV received Order: {order.orderId}")
    
    def on_instant_action_received(action: InstantActions):
        nonlocal received_instant_action
        received_instant_action = action
        instant_action_received.set()
        LOGGER.info(f"AGV received InstantActions: {action.actions[0].actionType}")
    
    agv.on_order_received(on_order_received)
    agv.on_instant_action(on_instant_action_received)
    
    # Create and store factsheet for AGV
    factsheet = Factsheet(
        headerId=1,
        timestamp="2025-01-01T12:00:00Z",
        version="2.1.0",
        manufacturer=manufacturer,
        serialNumber=serial_number,
        typeSpecification={
            "seriesName": "TestSeries",
            "agvKinematic": "DIFF",
            "agvClass": "FORKLIFT",
            "maxLoadMass": 500.0,
            "localizationTypes": ["NATURAL"],
            "navigationTypes": ["AUTONOMOUS"]
        },
        physicalParameters={
            "speedMin": 0.0, "speedMax": 1.0,
            "accelerationMax": 0.5, "decelerationMax": 0.5,
            "heightMax": 1.5, "width": 0.8, "length": 1.2
        },
        protocolLimits={
            "maxStringLens": {}, 
            "maxArrayLens": {}, 
            "timing": {"minOrderInterval": 0.5, "minStateInterval": 0.5}
        },
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
    
    # Connect AGV (this will publish ONLINE connection state and factsheet)
    agv._factsheet = factsheet  # Set factsheet before connect
    await agv.connect()
    LOGGER.info("AGV connected - should have published ONLINE connection state and factsheet")
    
    # 2. Start MasterControlClient
    master = MasterControlClient(
        broker_url=BROKER_URL,
        broker_port=BROKER_PORT,
        manufacturer="MasterControl",
        serial_number="MC001",
        validate_messages=True
    )
    
    # Register Master callbacks with proper signatures
    def on_connection_change(serial: str, connection_state: str):
        LOGGER.info(f"Master received connection change: {serial} -> {connection_state}")
        if connection_state == "ONLINE":
            connection_online_received.set()
        elif connection_state == "OFFLINE":
            connection_offline_received.set()
    
    def on_factsheet_received(serial: str, factsheet_msg: Factsheet):
        nonlocal received_factsheet
        received_factsheet = factsheet_msg
        factsheet_received.set()
        LOGGER.info(f"Master received Factsheet from {serial}: {factsheet_msg.typeSpecification.seriesName}")
    
    def on_state_update_received(serial: str, state_msg: State):
        nonlocal received_state
        received_state = state_msg
        state_received.set()
        LOGGER.info(f"Master received State from {serial}: operatingMode={state_msg.operatingMode}")
    
    master.on_connection_change(on_connection_change)
    master.on_factsheet(on_factsheet_received)
    master.on_state_update(on_state_update_received)
    
    await master.connect()
    LOGGER.info("Master connected")
    
    # Wait for AGV → Master messages (Connection ONLINE and Factsheet)
    LOGGER.info("Waiting for Connection ONLINE message...")
    await asyncio.wait_for(connection_online_received.wait(), timeout=10.0)
    assert connection_online_received.is_set(), "Connection ONLINE message not received"
    
    LOGGER.info("Waiting for Factsheet message...")
    await asyncio.wait_for(factsheet_received.wait(), timeout=10.0)
    assert factsheet_received.is_set(), "Factsheet message not received"
    assert received_factsheet is not None, "Factsheet message not stored"
    assert received_factsheet.serialNumber == serial_number, "Factsheet serial number mismatch"
    
    # 3. AGV sends State update
    state = State(
        headerId=2,
        timestamp="2025-01-01T12:00:01Z",
        version="2.1.0",
        manufacturer=manufacturer,
        serialNumber=serial_number,
        orderId="",
        orderUpdateId=0,
        lastNodeId="",
        lastNodeSequenceId=0,
        nodeStates=[],
        edgeStates=[],
        driving=False,
        actionStates=[],
        batteryState={"batteryCharge": 100.0, "charging": False},
        operatingMode="AUTOMATIC",
        errors=[],
        safetyState={"eStop": "NONE", "fieldViolation": False}
    )
    
    LOGGER.info("AGV sending State update...")
    await agv.send_state(state)
    
    LOGGER.info("Waiting for State message...")
    await asyncio.wait_for(state_received.wait(), timeout=10.0)
    assert state_received.is_set(), "State message not received"
    assert received_state is not None, "State message not stored"
    assert received_state.operatingMode == "AUTOMATIC", "State operating mode mismatch"
    
    # 4. Master sends an Order to AGV
    order = Order(
        headerId=3,
        timestamp="2025-01-01T12:00:02Z",
        version="2.1.0",
        manufacturer=manufacturer,
        serialNumber=serial_number,
        orderId="Order123",
        orderUpdateId=1,
        nodes=[{
            "nodeId": "N1",
            "sequenceId": 1,
            "released": True,
            "nodePosition": {"x": 0.0, "y": 0.0, "theta": 0.0},
            "nodeDescription": "Start position"
        }],
        edges=[{
            "edgeId": "E1",
            "sequenceId": 1,
            "released": True,
            "startNodeId": "N1",
            "endNodeId": "N1",
            "trajectory": {"degree": 3, "knotVector": [0.0, 0.0, 0.0, 1.0, 1.0, 1.0], "controlPoints": []}
        }]
    )
    
    LOGGER.info("Master sending Order to AGV...")
    await master.send_order(manufacturer, serial_number, order)
    
    LOGGER.info("Waiting for Order message...")
    await asyncio.wait_for(order_received.wait(), timeout=10.0)
    assert order_received.is_set(), "Order message not received"
    assert received_order is not None, "Order message not stored"
    assert received_order.orderId == "Order123", "Order ID mismatch"
    assert len(received_order.nodes) == 1, "Order nodes count mismatch"
    
    # 5. Master sends an InstantActions to AGV
    instant_action = InstantActions(
        headerId=4,
        timestamp="2025-01-01T12:00:03Z",
        version="2.1.0",
        manufacturer=manufacturer,
        serialNumber=serial_number,
        actions=[{
            "actionId": "A1",
            "actionType": "TEST",
            "blockingType": "NONE",
            "actionParameters": []
        }]
    )
    
    LOGGER.info("Master sending InstantActions to AGV...")
    await master.send_instant_action(manufacturer, serial_number, instant_action)
    
    LOGGER.info("Waiting for InstantActions message...")
    await asyncio.wait_for(instant_action_received.wait(), timeout=10.0)
    assert instant_action_received.is_set(), "InstantActions message not received"
    assert received_instant_action is not None, "InstantActions message not stored"
    assert len(received_instant_action.actions) == 1, "InstantActions actions count mismatch"
    assert received_instant_action.actions[0].actionType == "TEST", "InstantActions type mismatch"
    
    # 6. AGV disconnects → Master should receive OFFLINE connection state
    LOGGER.info("AGV disconnecting...")
    await agv.disconnect()  # This will publish OFFLINE connection state
    
    LOGGER.info("Waiting for Connection OFFLINE message...")
    await asyncio.wait_for(connection_offline_received.wait(), timeout=10.0)
    assert connection_offline_received.is_set(), "Connection OFFLINE message not received"
    
    # Cleanup
    await master.disconnect()
    
    # Final verification - all message flows completed successfully
    LOGGER.info("Integration smoke test completed successfully!")
    LOGGER.info("All six VDA5050 message flows verified:")
    LOGGER.info("✓ 1. Connection ONLINE")
    LOGGER.info("✓ 2. Factsheet")
    LOGGER.info("✓ 3. State")
    LOGGER.info("✓ 4. Order")
    LOGGER.info("✓ 5. InstantActions")
    LOGGER.info("✓ 6. Connection OFFLINE")
    
    # Additional validation assertions
    assert received_factsheet.manufacturer == manufacturer, "Factsheet manufacturer validation failed"
    assert received_factsheet.version == "2.1.0", "Factsheet version validation failed"
    assert received_state.manufacturer == manufacturer, "State manufacturer validation failed"
    assert received_state.version == "2.1.0", "State version validation failed"
    assert received_order.manufacturer == manufacturer, "Order manufacturer validation failed"
    assert received_order.version == "2.1.0", "Order version validation failed"
    assert received_instant_action.manufacturer == manufacturer, "InstantActions manufacturer validation failed"
    assert received_instant_action.version == "2.1.0", "InstantActions version validation failed"