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
    python agv_simulator.py [options]
    
    Examples:
    python agv_simulator.py --broker-url 192.168.1.100 --agv-serial AGV-002
    python agv_simulator.py --manufacturer MyCompany --broker-port 8883 --state-interval 1.0
    python agv_simulator.py --position-x 10.0 --position-y 5.0 --map-id warehouse_map
    python agv_simulator.py --no-movement --position-x 5.0 --position-y 5.0
    python agv_simulator.py --movement-speed 0.000005 --position-x 36.116731 --position-y 128.364716
"""

import argparse
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
from vda5050.models.base import AgvPosition
from vda5050.models.order import Order
from vda5050.models.instant_action import InstantActions

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION (Default values - can be overridden via command line)
# ============================================================================
DEFAULT_BROKER_URL = "127.0.0.1"
DEFAULT_BROKER_PORT = 1883
DEFAULT_AGV_MANUFACTURER = "RobotCompany"
DEFAULT_AGV_SERIAL = "AGV-001"
DEFAULT_VDA5050_VERSION = "2.1.0"
DEFAULT_STATE_UPDATE_INTERVAL = 2.0  # seconds

# AGV Position Configuration (Default values)
DEFAULT_POSITION_X = 0.0  # meters
DEFAULT_POSITION_Y = 0.0  # meters
DEFAULT_POSITION_THETA = 0.0  # radians
DEFAULT_MAP_ID = "default_map"
DEFAULT_POSITION_INITIALIZED = True
DEFAULT_ENABLE_MOVEMENT = True  # Whether to simulate position movement
DEFAULT_MOVEMENT_SPEED = 0.00001  # Movement speed in degrees per update (for lat/lon)


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

def create_factsheet(manufacturer: str, serial_number: str, version: str) -> Factsheet:
    """
    Create the AGV's factsheet with capabilities and specifications.
    
    The factsheet describes what the AGV can do and its physical properties.
    This is typically published once on connect and retained on the broker.
    """
    return Factsheet(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version=version,
        manufacturer=manufacturer,
        serialNumber=serial_number,
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


def create_state(header_id: int, battery_charge: float, driving: bool, manufacturer: str, serial_number: str, version: str, agv_position: AgvPosition) -> State:
    """
    Create a state message representing the current AGV status.
    
    This should be published periodically (e.g., every 1-2 seconds) to inform
    the Master Control system about the AGV's current state.
    """
    return State(
        headerId=header_id,
        timestamp=datetime.now(timezone.utc),
        version=version,
        manufacturer=manufacturer,
        serialNumber=serial_number,
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
        ),
        agvPosition=agv_position  # Current AGV position
    )


# ============================================================================
# AGV SIMULATOR
# ============================================================================

class AGVSimulator:
    """Simulates an AGV running VDA5050 protocol."""
    
    def __init__(self, broker_url: str, broker_port: int, manufacturer: str, 
                 serial_number: str, version: str, state_interval: float,
                 position_x: float, position_y: float, position_theta: float, 
                 map_id: str, position_initialized: bool, enable_movement: bool,
                 movement_speed: float):
        self.client: Optional[AGVClient] = None
        self.shutdown_event = asyncio.Event()
        self.state_header_id = 2  # Start from 2 (1 was used for factsheet)
        self.battery_charge = 95.0  # Initial battery level
        
        # Configuration parameters
        self.broker_url = broker_url
        self.broker_port = broker_port
        self.manufacturer = manufacturer
        self.serial_number = serial_number
        self.version = version
        self.state_interval = state_interval
        
        # Position configuration
        self.position_x = position_x
        self.position_y = position_y
        self.position_theta = position_theta
        self.map_id = map_id
        self.position_initialized = position_initialized
        self.enable_movement = enable_movement
        self.movement_speed = movement_speed
        
    async def setup_and_connect(self):
        """Setup AGVClient and connect to the broker."""
        logger.info("=" * 70)
        logger.info("AGV SIMULATOR - SETUP")
        logger.info("=" * 70)
        
        # Instantiate AGVClient with identity, version, and validation
        self.client = AGVClient(
            broker_url=self.broker_url,
            manufacturer=self.manufacturer,
            serial_number=self.serial_number,
            broker_port=self.broker_port,
            version=self.version,
            validate_messages=True  # Enable JSON schema validation
        )
        
        logger.info(f"AGV Identity: {self.manufacturer}/{self.serial_number}")
        logger.info(f"VDA5050 Version: {self.version}")
        logger.info(f"Broker: {self.broker_url}:{self.broker_port}")
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
        factsheet = create_factsheet(self.manufacturer, self.serial_number, self.version)
        await self.client.send_factsheet(factsheet)
        logger.info("✓ Factsheet published (retained)")
        logger.info("")
        
    async def state_publisher_loop(self):
        """Periodically publish state updates."""
        logger.info("=" * 70)
        logger.info("STATE PUBLISHER - STARTED")
        logger.info("=" * 70)
        logger.info(f"Publishing state every {self.state_interval} seconds")
        logger.info("Press Ctrl+C to stop")
        logger.info("")
        
        while not self.shutdown_event.is_set():
            # Simulate battery drain
            self.battery_charge = max(10.0, self.battery_charge - 0.1)
            
            # Simulate driving status (alternates for demo purposes)
            driving = (self.state_header_id % 4) < 2
            
            # Simulate position movement (simple circular motion for demo)
            if driving and self.enable_movement:
                # Move in a small circle for demonstration
                # Much slower movement suitable for lat/lon coordinates
                import math
                time_factor = self.state_header_id * 0.01  # Very slow movement
                # Move at configurable speed (realistic for AGV speed)
                # 1 degree ≈ 111,000 meters, so 0.00001 degrees ≈ 1.1 meters
                self.position_x += self.movement_speed * math.cos(time_factor)
                self.position_y += self.movement_speed * math.sin(time_factor)
                self.position_theta += 0.005  # Very slow rotation (0.005 radians ≈ 0.3 degrees)
            
            # Create current AGV position
            current_position = AgvPosition(
                x=self.position_x,
                y=self.position_y,
                theta=self.position_theta,
                mapId=self.map_id,
                positionInitialized=self.position_initialized,
                localizationScore=0.95  # High localization confidence
            )
            
            # Create and publish state
            state = create_state(
                header_id=self.state_header_id,
                battery_charge=self.battery_charge,
                driving=driving,
                manufacturer=self.manufacturer,
                serial_number=self.serial_number,
                version=self.version,
                agv_position=current_position
            )
            
            await self.client.send_state(state)
            logger.info(f"📊 State #{self.state_header_id}: "
                       f"battery={self.battery_charge:.1f}%, "
                       f"driving={driving}, "
                       f"pos=({self.position_x:.2f}, {self.position_y:.2f}, {self.position_theta:.2f})")
            
            self.state_header_id += 1
            
            # Wait for next update interval or shutdown
            try:
                await asyncio.wait_for(
                    self.shutdown_event.wait(),
                    timeout=self.state_interval
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
# COMMAND LINE ARGUMENT PARSING
# ============================================================================

def parse_arguments():
    """Parse command line arguments for AGV simulator configuration."""
    parser = argparse.ArgumentParser(
        description="AGV Simulator for VDA5050 protocol",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --broker-url 192.168.1.100 --agv-serial AGV-002
  %(prog)s --manufacturer MyCompany --broker-port 8883 --state-interval 1.0
  %(prog)s --position-x 10.0 --position-y 5.0 --map-id warehouse_map
  %(prog)s --no-movement --position-x 5.0 --position-y 5.0
  %(prog)s --movement-speed 0.000005 --position-x 36.116731 --position-y 128.364716
  %(prog)s --help
        """
    )
    
    # Broker configuration
    parser.add_argument(
        "--broker-url", 
        default=DEFAULT_BROKER_URL,
        help=f"MQTT broker URL (default: {DEFAULT_BROKER_URL})"
    )
    parser.add_argument(
        "--broker-port", 
        type=int, 
        default=DEFAULT_BROKER_PORT,
        help=f"MQTT broker port (default: {DEFAULT_BROKER_PORT})"
    )
    
    # AGV identity configuration
    parser.add_argument(
        "--manufacturer", 
        default=DEFAULT_AGV_MANUFACTURER,
        help=f"AGV manufacturer name (default: {DEFAULT_AGV_MANUFACTURER})"
    )
    parser.add_argument(
        "--agv-serial", 
        default=DEFAULT_AGV_SERIAL,
        help=f"AGV serial number (default: {DEFAULT_AGV_SERIAL})"
    )
    parser.add_argument(
        "--version", 
        default=DEFAULT_VDA5050_VERSION,
        help=f"VDA5050 protocol version (default: {DEFAULT_VDA5050_VERSION})"
    )
    
    # State update configuration
    parser.add_argument(
        "--state-interval", 
        type=float, 
        default=DEFAULT_STATE_UPDATE_INTERVAL,
        help=f"State update interval in seconds (default: {DEFAULT_STATE_UPDATE_INTERVAL})"
    )
    
    # AGV position configuration
    parser.add_argument(
        "--position-x", 
        type=float, 
        default=DEFAULT_POSITION_X,
        help=f"Initial X position in meters (default: {DEFAULT_POSITION_X})"
    )
    parser.add_argument(
        "--position-y", 
        type=float, 
        default=DEFAULT_POSITION_Y,
        help=f"Initial Y position in meters (default: {DEFAULT_POSITION_Y})"
    )
    parser.add_argument(
        "--position-theta", 
        type=float, 
        default=DEFAULT_POSITION_THETA,
        help=f"Initial orientation in radians (default: {DEFAULT_POSITION_THETA})"
    )
    parser.add_argument(
        "--map-id", 
        default=DEFAULT_MAP_ID,
        help=f"Map identifier (default: {DEFAULT_MAP_ID})"
    )
    parser.add_argument(
        "--position-initialized", 
        type=bool, 
        default=DEFAULT_POSITION_INITIALIZED,
        help=f"Whether position is initialized (default: {DEFAULT_POSITION_INITIALIZED})"
    )
    parser.add_argument(
        "--no-movement", 
        action="store_true",
        default=False,
        help="Disable position movement simulation (keep position static)"
    )
    parser.add_argument(
        "--movement-speed", 
        type=float, 
        default=DEFAULT_MOVEMENT_SPEED,
        help=f"Movement speed in degrees per update for lat/lon coordinates (default: {DEFAULT_MOVEMENT_SPEED})"
    )
    
    return parser.parse_args()


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main entry point."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Create simulator with parsed configuration
    simulator = AGVSimulator(
        broker_url=args.broker_url,
        broker_port=args.broker_port,
        manufacturer=args.manufacturer,
        serial_number=args.agv_serial,
        version=args.version,
        state_interval=args.state_interval,
        position_x=args.position_x,
        position_y=args.position_y,
        position_theta=args.position_theta,
        map_id=args.map_id,
        position_initialized=args.position_initialized,
        enable_movement=not args.no_movement,
        movement_speed=args.movement_speed
    )
    
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
    # Parse arguments early to show configuration
    args = parse_arguments()
    
    print(f"""
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
║  Configuration:                                                      ║
║  • Broker: {args.broker_url}:{args.broker_port:<5}                                    ║
║  • AGV: {args.manufacturer}/{args.agv_serial:<20}                         ║
║  • Version: {args.version:<15} State Interval: {args.state_interval}s              ║
║  • Position: ({args.position_x:.1f}, {args.position_y:.1f}, {args.position_theta:.1f}) Map: {args.map_id:<10} ║
║  • Movement: {'Disabled' if args.no_movement else 'Enabled':<10}                                            ║
╚══════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Already handled by signal handler

