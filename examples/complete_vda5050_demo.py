#!/usr/bin/env python3
"""
Complete VDA5050 Flow Demo
==========================

This single-script demo illustrates the complete VDA5050 flow in one self-contained example.

It covers:
- MQTT Broker Configuration: Point both clients at the same broker
- AGVClient Setup & Connect: Instantiate with identity and callbacks
- MasterControlClient Setup & Connect: Instantiate with callbacks
- Retained Connection & Factsheet: AGV publishes ONLINE state and factsheet on connect
- Periodic State Updates: AGV publishes state updates in a loop
- Sending Commands: Master sends an Order and InstantAction
- Graceful Shutdown: Both clients disconnect cleanly on SIGINT

Requirements:
- MQTT broker running (e.g., mosquitto on localhost:1883)
- Install: pip install vda5050-client

Usage:
    python complete_vda5050_demo.py
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone

# Import VDA5050 client components
from vda5050.clients.agv import AGVClient
from vda5050.clients.master_control import MasterControlClient
from vda5050.models.connection import ConnectionState
from vda5050.models.factsheet import (
    Factsheet, TypeSpecification, PhysicalParameters, ProtocolLimits,
    ProtocolFeatures, AgvGeometry, LoadSpecification,
    AgvKinematic, AgvClass, LocalizationType, NavigationType,
    MaxStringLens, MaxArrayLens, Timing
)
from vda5050.models.state import (
    State, BatteryState, SafetyState, EStop, OperatingMode
)
from vda5050.models.order import Order, Node, Edge
from vda5050.models.instant_action import InstantActions
from vda5050.models.base import Action, ActionParameter, BlockingType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# MQTT BROKER CONFIGURATION
# ============================================================================
BROKER_URL = "127.0.0.1"  # Change to your MQTT broker IP
BROKER_PORT = 1883

# AGV Identity
AGV_MANUFACTURER = "RobotCompany"
AGV_SERIAL = "AGV-001"

# Master Control Identity
MASTER_MANUFACTURER = "ControlSystem"
MASTER_SERIAL = "MASTER-001"

# VDA5050 Version
VDA5050_VERSION = "2.1.0"


# ============================================================================
# AGV CLIENT CALLBACKS
# ============================================================================

def on_order_received_callback(order: Order):
    """Called when AGV receives an order from master control."""
    logger.info(f"[AGV] 📦 Order received: orderId={order.orderId}, "
                f"orderUpdateId={order.orderUpdateId}, nodes={len(order.nodes)}, edges={len(order.edges)}")
    
    # In a real application, the AGV would:
    # 1. Validate the order
    # 2. Start path planning
    # 3. Begin executing the order
    # 4. Update state periodically with progress


def on_instant_action_callback(action: InstantActions):
    """Called when AGV receives an instant action from master control."""
    logger.info(f"[AGV] ⚡ InstantAction received: {len(action.actions)} action(s)")
    for act in action.actions:
        logger.info(f"[AGV]    - actionType={act.actionType}, actionId={act.actionId}")
    
    # In a real application, the AGV would:
    # 1. Execute the instant action immediately
    # 2. Update action states in the next state message


# ============================================================================
# MASTER CONTROL CLIENT CALLBACKS
# ============================================================================

def on_connection_change_callback(serial: str, connection_state: str):
    """Called when an AGV's connection state changes."""
    logger.info(f"[MASTER] 🔌 AGV {serial} connection changed: {connection_state}")


def on_factsheet_callback(serial: str, factsheet: Factsheet):
    """Called when an AGV publishes its factsheet."""
    logger.info(f"[MASTER] 📋 Factsheet received from {serial}:")
    logger.info(f"[MASTER]    - Series: {factsheet.typeSpecification.seriesName}")
    logger.info(f"[MASTER]    - Kinematic: {factsheet.typeSpecification.agvKinematic.value}")
    logger.info(f"[MASTER]    - Class: {factsheet.typeSpecification.agvClass.value}")
    logger.info(f"[MASTER]    - Max Load: {factsheet.typeSpecification.maxLoadMass} kg")


def on_state_update_callback(serial: str, state: State):
    """Called when an AGV publishes a state update."""
    logger.info(f"[MASTER] 📊 State update from {serial}: "
                f"battery={state.batteryState.batteryCharge}%, "
                f"driving={state.driving}, "
                f"operatingMode={state.operatingMode.value}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_sample_factsheet() -> Factsheet:
    """Create a sample factsheet for the AGV."""
    return Factsheet(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=AGV_MANUFACTURER,
        serialNumber=AGV_SERIAL,
        typeSpecification=TypeSpecification(
            seriesName="MowBot-3000",
            seriesDescription="Autonomous lawn mowing robot",
            agvKinematic=AgvKinematic.DIFF,
            agvClass=AgvClass.CARRIER,
            maxLoadMass=50.0,
            localizationTypes=[LocalizationType.NATURAL],
            navigationTypes=[NavigationType.AUTONOMOUS]
        ),
        physicalParameters=PhysicalParameters(
            speedMin=0.1,
            speedMax=2.0,
            accelerationMax=0.5,
            decelerationMax=0.8,
            heightMin=0.3,
            heightMax=0.5,
            width=0.8,
            length=1.2
        ),
        protocolLimits=ProtocolLimits(
            maxStringLens=MaxStringLens(
                msgLen=50000,
                topicSerialLen=100,
                topicElemLen=50,
                idLen=100,
                idNumericalOnly=False,
                enumLen=50,
                loadIdLen=100
            ),
            maxArrayLens=MaxArrayLens(
                order_nodes=100,
                order_edges=100,
                node_actions=10,
                edge_actions=10
            ),
            timing=Timing(
                minOrderInterval=1.0,
                minStateInterval=0.5,
                defaultStateInterval=1.0,
                visualizationInterval=0.1
            )
        ),
        protocolFeatures=ProtocolFeatures(
            optionalParameters=[],
            agvActions=[]
        ),
        agvGeometry=AgvGeometry(),
        loadSpecification=LoadSpecification()
    )


def create_sample_state(header_id: int) -> State:
    """Create a sample state message for the AGV."""
    return State(
        headerId=header_id,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=AGV_MANUFACTURER,
        serialNumber=AGV_SERIAL,
        orderId="",  # No active order
        orderUpdateId=0,
        lastNodeId="",
        lastNodeSequenceId=0,
        driving=False,
        paused=False,
        operatingMode=OperatingMode.AUTOMATIC,
        nodeStates=[],
        edgeStates=[],
        actionStates=[],
        batteryState=BatteryState(
            batteryCharge=85.5,
            batteryVoltage=48.2,
            charging=False,
            reach=5000.0
        ),
        errors=[],
        safetyState=SafetyState(
            eStop=EStop.NONE,
            fieldViolation=False
        )
    )


def create_sample_order() -> Order:
    """Create a sample order for the AGV."""
    return Order(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=AGV_MANUFACTURER,
        serialNumber=AGV_SERIAL,
        orderId="ORDER-12345",
        orderUpdateId=0,
        nodes=[
            Node(
                nodeId="node_1",
                sequenceId=0,
                released=True,
                actions=[]
            ),
            Node(
                nodeId="node_2",
                sequenceId=2,
                released=True,
                actions=[
                    Action(
                        actionType="startMowing",
                        actionId="mow_action_1",
                        blockingType=BlockingType.NONE,
                        actionParameters=[]
                    )
                ]
            )
        ],
        edges=[
            Edge(
                edgeId="edge_1_2",
                sequenceId=1,
                released=True,
                startNodeId="node_1",
                endNodeId="node_2",
                actions=[]
            )
        ]
    )


def create_sample_instant_action() -> InstantActions:
    """Create a sample instant action."""
    return InstantActions(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=AGV_MANUFACTURER,
        serialNumber=AGV_SERIAL,
        actions=[
            Action(
                actionType="pauseMovement",
                actionId="pause_1",
                blockingType=BlockingType.HARD,
                actionParameters=[]
            )
        ]
    )


# ============================================================================
# MAIN DEMO
# ============================================================================

class VDA5050Demo:
    """Manages the complete VDA5050 demo flow."""
    
    def __init__(self):
        self.agv_client: Optional[AGVClient] = None
        self.master_client: Optional[MasterControlClient] = None
        self.shutdown_event = asyncio.Event()
        self.state_header_id = 2  # Start from 2 (1 was used for factsheet)
        self.first_state_received = asyncio.Event()
        
    async def setup_agv_client(self):
        """Setup and connect the AGV client."""
        logger.info("=" * 70)
        logger.info("SETTING UP AGV CLIENT")
        logger.info("=" * 70)
        
        # Instantiate AGVClient with identity and validation enabled
        self.agv_client = AGVClient(
            broker_url=BROKER_URL,
            manufacturer=AGV_MANUFACTURER,
            serial_number=AGV_SERIAL,
            broker_port=BROKER_PORT,
            version=VDA5050_VERSION,
            validate_messages=True  # Enable JSON schema validation
        )
        
        # Register callbacks
        self.agv_client.on_order_received(on_order_received_callback)
        self.agv_client.on_instant_action(on_instant_action_callback)
        
        # Connect to MQTT broker
        logger.info(f"[AGV] Connecting to broker at {BROKER_URL}:{BROKER_PORT}...")
        success = await self.agv_client.connect()
        
        if not success:
            raise RuntimeError("Failed to connect AGV client")
        
        logger.info("[AGV] ✅ Connected successfully")
        
        # AGV automatically publishes ONLINE connection state and factsheet on connect
        # via the _on_vda5050_connect() hook. Let's also send the factsheet explicitly:
        factsheet = create_sample_factsheet()
        await self.agv_client.send_factsheet(factsheet)
        logger.info("[AGV] 📋 Published factsheet (retained)")
        
        logger.info("")
    
    async def setup_master_client(self):
        """Setup and connect the Master Control client."""
        logger.info("=" * 70)
        logger.info("SETTING UP MASTER CONTROL CLIENT")
        logger.info("=" * 70)
        
        # Instantiate MasterControlClient with a different identity
        self.master_client = MasterControlClient(
            broker_url=BROKER_URL,
            manufacturer=MASTER_MANUFACTURER,
            serial_number=MASTER_SERIAL,
            broker_port=BROKER_PORT,
            version=VDA5050_VERSION,
            validate_messages=True
        )
        
        # Register callbacks with an inner wrapper to track first state
        def on_state_wrapper(serial: str, state: State):
            on_state_update_callback(serial, state)
            # Signal that we've received the first state
            if not self.first_state_received.is_set():
                self.first_state_received.set()
        
        self.master_client.on_connection_change(on_connection_change_callback)
        self.master_client.on_factsheet(on_factsheet_callback)
        self.master_client.on_state_update(on_state_wrapper)
        
        # Connect to MQTT broker
        logger.info(f"[MASTER] Connecting to broker at {BROKER_URL}:{BROKER_PORT}...")
        success = await self.master_client.connect()
        
        if not success:
            raise RuntimeError("Failed to connect Master Control client")
        
        logger.info("[MASTER] ✅ Connected successfully")
        logger.info("[MASTER] 📡 Subscribed to all AGV topics (wildcards)")
        logger.info("")
        
        # Brief delay to receive retained messages
        await asyncio.sleep(1)
    
    async def agv_state_publisher(self):
        """Periodically publish AGV state updates."""
        logger.info("=" * 70)
        logger.info("STARTING PERIODIC STATE UPDATES")
        logger.info("=" * 70)
        logger.info("[AGV] Publishing state every 2 seconds...")
        logger.info("")
        
        while not self.shutdown_event.is_set():
            # Create and publish state
            state = create_sample_state(self.state_header_id)
            await self.agv_client.send_state(state)
            self.state_header_id += 1
            
            # Wait 2 seconds or until shutdown
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=2.0
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                continue  # Continue publishing
    
    async def master_send_commands(self):
        """Master control sends commands after receiving first state."""
        # Wait for first state update from AGV
        logger.info("[MASTER] Waiting for first state update from AGV...")
        await self.first_state_received.wait()
        
        logger.info("")
        logger.info("=" * 70)
        logger.info("MASTER SENDING COMMANDS")
        logger.info("=" * 70)
        
        # Wait a bit before sending order
        await asyncio.sleep(2)
        
        # Send an Order
        logger.info("[MASTER] 📤 Sending Order to AGV...")
        order = create_sample_order()
        success = await self.master_client.send_order(
            target_manufacturer=AGV_MANUFACTURER,
            target_serial=AGV_SERIAL,
            order=order
        )
        if success:
            logger.info("[MASTER] ✅ Order sent successfully")
        else:
            logger.error("[MASTER] ❌ Failed to send order")
        
        # Wait a bit before sending instant action
        await asyncio.sleep(2)
        
        # Send an InstantAction
        logger.info("[MASTER] 📤 Sending InstantAction to AGV...")
        instant_action = create_sample_instant_action()
        success = await self.master_client.send_instant_action(
            target_manufacturer=AGV_MANUFACTURER,
            target_serial=AGV_SERIAL,
            action=instant_action
        )
        if success:
            logger.info("[MASTER] ✅ InstantAction sent successfully")
        else:
            logger.error("[MASTER] ❌ Failed to send instant action")
        
        logger.info("")
    
    async def graceful_shutdown(self):
        """Gracefully shutdown both clients."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("GRACEFUL SHUTDOWN")
        logger.info("=" * 70)
        
        # Disconnect AGV (will publish OFFLINE state automatically)
        if self.agv_client:
            logger.info("[AGV] Disconnecting...")
            await self.agv_client.disconnect()
            logger.info("[AGV] ✅ Disconnected (OFFLINE state published)")
        
        # Disconnect Master
        if self.master_client:
            logger.info("[MASTER] Disconnecting...")
            await self.master_client.disconnect()
            logger.info("[MASTER] ✅ Disconnected")
        
        logger.info("")
        logger.info("Demo completed successfully! 🎉")
    
    async def run(self):
        """Run the complete demo."""
        try:
            # Setup both clients
            await self.setup_agv_client()
            await self.setup_master_client()
            
            # Start periodic state publishing in background
            state_task = asyncio.create_task(self.agv_state_publisher())
            
            # Start master command sending in background
            master_task = asyncio.create_task(self.master_send_commands())
            
            # Wait for shutdown signal or tasks to complete
            logger.info("Demo running... Press Ctrl+C to stop.")
            logger.info("")
            
            # Run for a limited time (10 seconds) or until interrupted
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.info("[DEMO] Time limit reached, shutting down...")
                self.shutdown_event.set()
            
            # Wait for tasks to complete
            await asyncio.gather(state_task, master_task, return_exceptions=True)
            
        finally:
            await self.graceful_shutdown()


async def main():
    """Main entry point."""
    demo = VDA5050Demo()
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("\n[DEMO] Received shutdown signal (Ctrl+C)")
        demo.shutdown_event.set()
    
    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await demo.run()
    except KeyboardInterrupt:
        pass  # Already handled by signal handler
    except Exception as e:
        logger.error(f"Demo error: {e}", exc_info=True)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                   VDA5050 Complete Flow Demo                         ║
║                                                                      ║
║  This demo illustrates the complete VDA5050 protocol flow:          ║
║  • MQTT broker connection                                           ║
║  • AGV client with callbacks                                        ║
║  • Master control client with callbacks                             ║
║  • Retained connection & factsheet                                  ║
║  • Periodic state updates                                           ║
║  • Command sending (Order & InstantAction)                          ║
║  • Graceful shutdown                                                ║
║                                                                      ║
║  Make sure an MQTT broker is running on 127.0.0.1:1883             ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")

