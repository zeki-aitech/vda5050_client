#!/usr/bin/env python3
"""
AGV Simulator Example
=====================

This script simulates an AGV that connects to a VDA5050 system via MQTT.

It demonstrates:
- Broker configuration and connection
- AGVClient instantiation with identity and validation
- Registering callbacks for orders and instant actions
- Publishing factsheet (retained) on connect
- Periodic state updates in a timed loop
- Graceful shutdown with OFFLINE state publication

Requirements:
- MQTT broker running (e.g., mosquitto on localhost:1883)
- Install: pip install vda5050-client

Usage:
    python agv_simulator.py
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Optional

# Import VDA5050 AGV client components
from vda5050.clients.agv import AGVClient
from vda5050.models.factsheet import (
    Factsheet, TypeSpecification, PhysicalParameters, ProtocolLimits,
    ProtocolFeatures, AgvGeometry, LoadSpecification,
    AgvKinematic, AgvClass, LocalizationType, NavigationType,
    MaxStringLens, MaxArrayLens, Timing
)
from vda5050.models.state import (
    State, BatteryState, SafetyState, EStop, OperatingMode
)
from vda5050.models.order import Order
from vda5050.models.instant_action import InstantActions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# BROKER CONFIGURATION
# ============================================================================
BROKER_URL = "127.0.0.1"  # Change to your MQTT broker IP
BROKER_PORT = 1883

# AGV Identity Configuration
AGV_MANUFACTURER = "RobotCompany"
AGV_SERIAL = "AGV-001"
VDA5050_VERSION = "2.1.0"

# State Update Configuration
STATE_UPDATE_INTERVAL = 2.0  # seconds


# ============================================================================
# CALLBACKS
# ============================================================================

def on_order_received(order: Order):
    """
    Callback invoked when an Order message is received from Master Control.
    
    In a real AGV, this would:
    - Validate the order against current state
    - Begin path planning
    - Execute the order nodes and edges
    - Update state with progress
    """
    logger.info(f"📦 ORDER RECEIVED:")
    logger.info(f"   Order ID: {order.orderId}")
    logger.info(f"   Order Update ID: {order.orderUpdateId}")
    logger.info(f"   Nodes: {len(order.nodes)}")
    logger.info(f"   Edges: {len(order.edges)}")
    
    if order.nodes:
        logger.info(f"   First Node: {order.nodes[0].nodeId}")
        if len(order.nodes) > 1:
            logger.info(f"   Last Node: {order.nodes[-1].nodeId}")
    
    # In real implementation: Start executing the order
    logger.info("   → Order accepted and execution started")


def on_instant_action(action: InstantActions):
    """
    Callback invoked when an InstantAction message is received from Master Control.
    
    In a real AGV, this would:
    - Execute the action immediately
    - Update action states in the next state message
    - Handle blocking behavior according to blockingType
    """
    logger.info(f"⚡ INSTANT ACTION RECEIVED:")
    logger.info(f"   Number of actions: {len(action.actions)}")
    
    for act in action.actions:
        logger.info(f"   Action Type: {act.actionType}")
        logger.info(f"   Action ID: {act.actionId}")
        logger.info(f"   Blocking Type: {act.blockingType.value}")
        
        if act.actionParameters:
            logger.info(f"   Parameters:")
            for param in act.actionParameters:
                logger.info(f"      - {param.key}: {param.value}")
    
    # In real implementation: Execute the instant action
    logger.info("   → InstantAction executed")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_factsheet() -> Factsheet:
    """
    Create the AGV's factsheet with capabilities and specifications.
    
    The factsheet describes what the AGV can do and its physical properties.
    This is typically published once on connect and retained on the broker.
    """
    return Factsheet(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=AGV_MANUFACTURER,
        serialNumber=AGV_SERIAL,
        typeSpecification=TypeSpecification(
            seriesName="MowBot-3000",
            seriesDescription="Autonomous lawn mowing robot with differential drive",
            agvKinematic=AgvKinematic.DIFF,
            agvClass=AgvClass.CARRIER,
            maxLoadMass=50.0,  # kg
            localizationTypes=[LocalizationType.NATURAL],
            navigationTypes=[NavigationType.AUTONOMOUS]
        ),
        physicalParameters=PhysicalParameters(
            speedMin=0.1,      # m/s
            speedMax=2.0,      # m/s
            accelerationMax=0.5,   # m/s²
            decelerationMax=0.8,   # m/s²
            heightMin=0.3,     # m
            heightMax=0.5,     # m
            width=0.8,         # m
            length=1.2         # m
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
                edge_actions=10,
                actions_actionsParameters=20,
                instantActions=5,
                state_nodeStates=50,
                state_edgeStates=50,
                state_actionStates=20,
                state_errors=10
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


def create_state(header_id: int, battery_charge: float, driving: bool) -> State:
    """
    Create a state message representing the current AGV status.
    
    This should be published periodically (e.g., every 1-2 seconds) to inform
    the Master Control system about the AGV's current state.
    """
    return State(
        headerId=header_id,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=AGV_MANUFACTURER,
        serialNumber=AGV_SERIAL,
        orderId="",  # Empty if no active order
        orderUpdateId=0,
        lastNodeId="",  # Last reached node ID
        lastNodeSequenceId=0,
        driving=driving,
        paused=False,
        operatingMode=OperatingMode.AUTOMATIC,
        nodeStates=[],  # List of nodes in current base/horizon
        edgeStates=[],  # List of edges in current base/horizon
        actionStates=[],  # List of active/completed actions
        batteryState=BatteryState(
            batteryCharge=battery_charge,
            batteryVoltage=48.2,
            charging=False,
            reach=5000.0  # meters
        ),
        errors=[],  # List of active errors
        safetyState=SafetyState(
            eStop=EStop.NONE,
            fieldViolation=False
        )
    )


# ============================================================================
# AGV SIMULATOR
# ============================================================================

class AGVSimulator:
    """Simulates an AGV running VDA5050 protocol."""
    
    def __init__(self):
        self.client: Optional[AGVClient] = None
        self.shutdown_event = asyncio.Event()
        self.state_header_id = 2  # Start from 2 (1 was used for factsheet)
        self.battery_charge = 95.0  # Initial battery level
        
    async def setup_and_connect(self):
        """Setup AGVClient and connect to the broker."""
        logger.info("=" * 70)
        logger.info("AGV SIMULATOR - SETUP")
        logger.info("=" * 70)
        
        # Instantiate AGVClient with identity, version, and validation
        self.client = AGVClient(
            broker_url=BROKER_URL,
            manufacturer=AGV_MANUFACTURER,
            serial_number=AGV_SERIAL,
            broker_port=BROKER_PORT,
            version=VDA5050_VERSION,
            validate_messages=True  # Enable JSON schema validation
        )
        
        logger.info(f"AGV Identity: {AGV_MANUFACTURER}/{AGV_SERIAL}")
        logger.info(f"VDA5050 Version: {VDA5050_VERSION}")
        logger.info(f"Broker: {BROKER_URL}:{BROKER_PORT}")
        logger.info("")
        
        # Register callbacks
        self.client.on_order_received(on_order_received)
        self.client.on_instant_action(on_instant_action)
        logger.info("✓ Callbacks registered")
        
        # Connect to broker
        logger.info(f"Connecting to MQTT broker...")
        success = await self.client.connect()
        
        if not success:
            raise RuntimeError("Failed to connect to MQTT broker")
        
        logger.info("✓ Connected to broker")
        logger.info("✓ Published ONLINE connection state (retained)")
        
        # Explicitly publish factsheet (retained)
        logger.info("")
        logger.info("Publishing factsheet...")
        factsheet = create_factsheet()
        await self.client.send_factsheet(factsheet)
        logger.info("✓ Factsheet published (retained)")
        logger.info("")
        
    async def state_publisher_loop(self):
        """Periodically publish state updates."""
        logger.info("=" * 70)
        logger.info("STATE PUBLISHER - STARTED")
        logger.info("=" * 70)
        logger.info(f"Publishing state every {STATE_UPDATE_INTERVAL} seconds")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        
        while not self.shutdown_event.is_set():
            # Simulate battery drain
            self.battery_charge = max(10.0, self.battery_charge - 0.1)
            
            # Simulate driving status (alternates for demo purposes)
            driving = (self.state_header_id % 4) < 2
            
            # Create and publish state
            state = create_state(
                header_id=self.state_header_id,
                battery_charge=self.battery_charge,
                driving=driving
            )
            
            await self.client.send_state(state)
            logger.info(f"📊 State #{self.state_header_id}: "
                       f"battery={self.battery_charge:.1f}%, "
                       f"driving={driving}")
            
            self.state_header_id += 1
            
            # Wait for next update interval or shutdown
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=STATE_UPDATE_INTERVAL
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                continue  # Continue publishing
    
    async def shutdown(self):
        """Gracefully disconnect from the broker."""
        logger.info("")
        logger.info("=" * 70)
        logger.info("SHUTDOWN")
        logger.info("=" * 70)
        
        if self.client:
            logger.info("Disconnecting from broker...")
            await self.client.disconnect()
            logger.info("✓ Disconnected from broker")
            logger.info("✓ Published OFFLINE connection state (retained)")
        
        logger.info("")
        logger.info("AGV simulator stopped successfully")
    
    async def run(self):
        """Run the AGV simulator."""
        try:
            await self.setup_and_connect()
            await self.state_publisher_loop()
        finally:
            await self.shutdown()


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point."""
    simulator = AGVSimulator()
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("\n🛑 Shutdown signal received (Ctrl+C)")
        simulator.shutdown_event.set()
    
    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await simulator.run()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                      AGV Simulator (VDA5050)                         ║
║                                                                      ║
║  This simulator demonstrates an AGV that:                           ║
║  • Connects to an MQTT broker                                       ║
║  • Publishes its factsheet and connection state (retained)          ║
║  • Publishes periodic state updates                                 ║
║  • Receives and processes orders from Master Control                ║
║  • Receives and executes instant actions                            ║
║  • Gracefully shuts down with OFFLINE state                         ║
║                                                                      ║
║  Make sure an MQTT broker is running on 127.0.0.1:1883             ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled by signal handler

