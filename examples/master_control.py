#!/usr/bin/env python3
"""
Master Control Example
======================

This script simulates a Master Control system that manages AGVs via VDA5050.

It demonstrates:
- Broker configuration and connection
- MasterControlClient instantiation with identity and validation
- Registering callbacks for connection changes, factsheets, and state updates
- Subscribing to all AGV topics via wildcards
- Receiving retained messages (connection state and factsheet)
- Sending orders and instant actions to specific AGVs
- Graceful shutdown

Requirements:
- MQTT broker running (e.g., mosquitto on localhost:1883)
- Install: pip install vda5050-client
- AGV(s) running (e.g., agv_simulator.py)

Usage:
    python master_control.py
"""

import asyncio
import logging
import signal
from datetime import datetime, timezone
from typing import Optional

# Import VDA5050 Master Control client components
from vda5050.clients.master_control import MasterControlClient
from vda5050.models.factsheet import Factsheet
from vda5050.models.state import State
from vda5050.models.order import Order, Node, Edge
from vda5050.models.instant_action import InstantActions
from vda5050.models.base import Action, BlockingType

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

# Master Control Identity Configuration
MASTER_MANUFACTURER = "ControlSystem"
MASTER_SERIAL = "MASTER-001"
VDA5050_VERSION = "2.1.0"

# Target AGV Configuration (for sending commands)
TARGET_AGV_MANUFACTURER = "RobotCompany"
TARGET_AGV_SERIAL = "AGV-001"


# ============================================================================
# CALLBACKS
# ============================================================================

def on_connection_change(serial: str, connection_state: str):
    """
    Callback invoked when an AGV's connection state changes.
    
    This is useful for:
    - Detecting when AGVs come online or go offline
    - Tracking fleet availability
    - Triggering alerts for unexpected disconnections
    """
    if connection_state == "ONLINE":
        logger.info(f"🟢 AGV {serial} is now ONLINE")
    elif connection_state == "OFFLINE":
        logger.info(f"🔴 AGV {serial} is now OFFLINE")
    else:
        logger.info(f"🔌 AGV {serial} connection state: {connection_state}")


def on_factsheet(serial: str, factsheet: Factsheet):
    """
    Callback invoked when an AGV publishes its factsheet.
    
    The factsheet contains static information about the AGV's capabilities.
    This is typically received once when the AGV connects (retained message).
    """
    logger.info(f"📋 FACTSHEET received from AGV {serial}:")
    logger.info(f"   Series: {factsheet.typeSpecification.seriesName}")
    
    if factsheet.typeSpecification.seriesDescription:
        logger.info(f"   Description: {factsheet.typeSpecification.seriesDescription}")
    
    logger.info(f"   Kinematic: {factsheet.typeSpecification.agvKinematic.value}")
    logger.info(f"   Class: {factsheet.typeSpecification.agvClass.value}")
    logger.info(f"   Max Load: {factsheet.typeSpecification.maxLoadMass} kg")
    logger.info(f"   Speed: {factsheet.physicalParameters.speedMin} - "
               f"{factsheet.physicalParameters.speedMax} m/s")
    logger.info(f"   Dimensions: {factsheet.physicalParameters.length}m × "
               f"{factsheet.physicalParameters.width}m × "
               f"{factsheet.physicalParameters.heightMax}m")
    logger.info(f"   Localization: {[t.value for t in factsheet.typeSpecification.localizationTypes]}")
    logger.info(f"   Navigation: {[t.value for t in factsheet.typeSpecification.navigationTypes]}")


def on_state_update(serial: str, state: State):
    """
    Callback invoked when an AGV publishes a state update.
    
    State updates are sent periodically (typically every 1-2 seconds) and
    contain the AGV's current status, position, battery, errors, etc.
    """
    # Log essential state information
    logger.info(f"📊 STATE from AGV {serial}:")
    logger.info(f"   Battery: {state.batteryState.batteryCharge:.1f}% "
               f"({'charging' if state.batteryState.charging else 'not charging'})")
    logger.info(f"   Driving: {state.driving}")
    logger.info(f"   Operating Mode: {state.operatingMode.value}")
    
    if state.orderId:
        logger.info(f"   Active Order: {state.orderId} (update {state.orderUpdateId})")
    
    if state.lastNodeId:
        logger.info(f"   Last Node: {state.lastNodeId} (seq {state.lastNodeSequenceId})")
    
    if state.paused:
        logger.info(f"   ⚠️  PAUSED")
    
    if state.errors:
        logger.info(f"   ⚠️  ERRORS: {len(state.errors)} active error(s)")
        for error in state.errors:
            logger.info(f"      - {error.errorType}: {error.errorDescription}")
    
    if state.safetyState.eStop != "NONE":
        logger.info(f"   🚨 E-STOP: {state.safetyState.eStop}")
    
    if state.actionStates:
        logger.info(f"   Actions: {len(state.actionStates)} action(s)")
        for action_state in state.actionStates:
            logger.info(f"      - {action_state.actionId}: {action_state.actionStatus.value}")


# ============================================================================
# COMMAND HELPERS
# ============================================================================

def create_sample_order(target_manufacturer: str, target_serial: str) -> Order:
    """
    Create a sample order to send to an AGV.
    
    In a real system, this would be generated based on:
    - Task requirements
    - AGV capabilities
    - Current map and navigation graph
    - Load handling requirements
    """
    return Order(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=target_manufacturer,
        serialNumber=target_serial,
        orderId=f"ORDER-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        orderUpdateId=0,
        nodes=[
            Node(
                nodeId="warehouse_pickup",
                sequenceId=0,
                released=True,
                actions=[]
            ),
            Node(
                nodeId="delivery_zone_A",
                sequenceId=2,
                released=True,
                actions=[
                    Action(
                        actionType="dropLoad",
                        actionId="drop_action_1",
                        blockingType=BlockingType.HARD,
                        actionParameters=[]
                    )
                ]
            ),
            Node(
                nodeId="charging_station",
                sequenceId=4,
                released=False,  # Horizon node
                actions=[]
            )
        ],
        edges=[
            Edge(
                edgeId="edge_warehouse_to_delivery",
                sequenceId=1,
                released=True,
                startNodeId="warehouse_pickup",
                endNodeId="delivery_zone_A",
                actions=[]
            ),
            Edge(
                edgeId="edge_delivery_to_charging",
                sequenceId=3,
                released=False,  # Horizon edge
                startNodeId="delivery_zone_A",
                endNodeId="charging_station",
                actions=[]
            )
        ]
    )


def create_sample_instant_action(target_manufacturer: str, target_serial: str) -> InstantActions:
    """
    Create a sample instant action to send to an AGV.
    
    Instant actions are executed immediately, regardless of current order state.
    Common use cases: pause, resume, emergency stop, status request, etc.
    """
    return InstantActions(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=VDA5050_VERSION,
        manufacturer=target_manufacturer,
        serialNumber=target_serial,
        actions=[
            Action(
                actionType="pauseMovement",
                actionId=f"pause_{datetime.now().strftime('%H%M%S')}",
                blockingType=BlockingType.HARD,
                actionParameters=[]
            )
        ]
    )


# ============================================================================
# MASTER CONTROL
# ============================================================================

class MasterControl:
    """Simulates a Master Control system managing AGVs."""
    
    def __init__(self):
        self.client: Optional[MasterControlClient] = None
        self.shutdown_event = asyncio.Event()
        self.first_state_received = asyncio.Event()
        
    async def setup_and_connect(self):
        """Setup MasterControlClient and connect to the broker."""
        logger.info("=" * 70)
        logger.info("MASTER CONTROL - SETUP")
        logger.info("=" * 70)
        
        # Instantiate MasterControlClient with identity, version, and validation
        self.client = MasterControlClient(
            broker_url=BROKER_URL,
            manufacturer=MASTER_MANUFACTURER,
            serial_number=MASTER_SERIAL,
            broker_port=BROKER_PORT,
            version=VDA5050_VERSION,
            validate_messages=True  # Enable JSON schema validation
        )
        
        logger.info(f"Master Identity: {MASTER_MANUFACTURER}/{MASTER_SERIAL}")
        logger.info(f"VDA5050 Version: {VDA5050_VERSION}")
        logger.info(f"Broker: {BROKER_URL}:{BROKER_PORT}")
        logger.info("")
        
        # Register callbacks with wrapper to track first state
        def on_state_wrapper(serial: str, state: State):
            on_state_update(serial, state)
            if not self.first_state_received.is_set():
                self.first_state_received.set()
        
        self.client.on_connection_change(on_connection_change)
        self.client.on_factsheet(on_factsheet)
        self.client.on_state_update(on_state_wrapper)
        logger.info("✓ Callbacks registered")
        
        # Connect to broker
        logger.info(f"Connecting to MQTT broker...")
        success = await self.client.connect()
        
        if not success:
            raise RuntimeError("Failed to connect to MQTT broker")
        
        logger.info("✓ Connected to broker")
        logger.info("✓ Subscribed to all AGV topics (wildcards)")
        logger.info("")
        
        # Wait briefly for retained messages (ONLINE state and Factsheet)
        logger.info("Waiting for retained messages from AGVs...")
        await asyncio.sleep(2)
        logger.info("")
    
    async def send_commands(self):
        """Send commands to the target AGV."""
        logger.info("=" * 70)
        logger.info("COMMAND SENDER")
        logger.info("=" * 70)
        
        # Wait for first state update to ensure AGV is connected
        logger.info(f"Waiting for state update from {TARGET_AGV_SERIAL}...")
        try:
            await asyncio.wait_for(self.first_state_received.wait(), timeout=10.0)
            logger.info(f"✓ Received state from {TARGET_AGV_SERIAL}")
        except asyncio.TimeoutError:
            logger.warning(f"⚠️  No state received from {TARGET_AGV_SERIAL} within timeout")
            logger.warning("   Commands will still be sent, but AGV may not be connected")
        
        logger.info("")
        
        # Send an Order
        logger.info(f"📤 Sending ORDER to {TARGET_AGV_MANUFACTURER}/{TARGET_AGV_SERIAL}...")
        order = create_sample_order(TARGET_AGV_MANUFACTURER, TARGET_AGV_SERIAL)
        logger.info(f"   Order ID: {order.orderId}")
        logger.info(f"   Nodes: {len(order.nodes)} ({len([n for n in order.nodes if n.released])} released)")
        logger.info(f"   Edges: {len(order.edges)} ({len([e for e in order.edges if e.released])} released)")
        
        success = await self.client.send_order(
            target_manufacturer=TARGET_AGV_MANUFACTURER,
            target_serial=TARGET_AGV_SERIAL,
            order=order
        )
        
        if success:
            logger.info("   ✅ Order sent successfully")
        else:
            logger.error("   ❌ Failed to send order")
        
        logger.info("")
        
        # Wait a bit before sending instant action
        await asyncio.sleep(3)
        
        # Send an InstantAction
        logger.info(f"📤 Sending INSTANT ACTION to {TARGET_AGV_MANUFACTURER}/{TARGET_AGV_SERIAL}...")
        instant_action = create_sample_instant_action(TARGET_AGV_MANUFACTURER, TARGET_AGV_SERIAL)
        logger.info(f"   Action Type: {instant_action.actions[0].actionType}")
        logger.info(f"   Action ID: {instant_action.actions[0].actionId}")
        
        success = await self.client.send_instant_action(
            target_manufacturer=TARGET_AGV_MANUFACTURER,
            target_serial=TARGET_AGV_SERIAL,
            action=instant_action
        )
        
        if success:
            logger.info("   ✅ InstantAction sent successfully")
        else:
            logger.error("   ❌ Failed to send instant action")
        
        logger.info("")
    
    async def monitor_loop(self):
        """Monitor AGVs until shutdown."""
        logger.info("=" * 70)
        logger.info("MONITORING MODE")
        logger.info("=" * 70)
        logger.info("Listening for AGV updates... Press Ctrl+C to stop")
        logger.info("")
        
        # Just wait for shutdown signal
        # All updates are handled by callbacks
        await self.shutdown_event.wait()
    
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
        
        logger.info("")
        logger.info("Master Control stopped successfully")
    
    async def run(self):
        """Run the Master Control system."""
        try:
            await self.setup_and_connect()
            
            # Send initial commands
            await self.send_commands()
            
            # Continue monitoring
            await self.monitor_loop()
            
        finally:
            await self.shutdown()


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point."""
    master = MasterControl()
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("\n🛑 Shutdown signal received (Ctrl+C)")
        master.shutdown_event.set()
    
    # Register signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await master.run()
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                   Master Control (VDA5050)                           ║
║                                                                      ║
║  This Master Control system demonstrates:                           ║
║  • Connecting to an MQTT broker                                     ║
║  • Subscribing to all AGV topics (wildcards)                        ║
║  • Receiving retained messages (connection & factsheet)             ║
║  • Monitoring AGV state updates in real-time                        ║
║  • Sending orders to specific AGVs                                  ║
║  • Sending instant actions to specific AGVs                         ║
║  • Graceful shutdown                                                ║
║                                                                      ║
║  Make sure:                                                         ║
║  1. MQTT broker is running on 127.0.0.1:1883                       ║
║  2. AGV(s) are running (e.g., agv_simulator.py)                    ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled by signal handler

