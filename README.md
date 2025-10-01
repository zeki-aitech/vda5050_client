# VDA5050 Python Client Library

A comprehensive Python client library for implementing VDA5050 AGV (Automated Guided Vehicle) communication protocol. This library provides both AGV and Master Control clients with full MQTT integration, message validation, and callback-based event handling.

## Project Overview

### Project Structure

```
vda5050_client/
├── src/vda5050/                    # Main library source code
│   ├── clients/                    # Client implementations
│   │   ├── agv.py                 # AGV client for receiving orders/actions
│   │   └── master_control.py      # Master control client for sending commands
│   ├── core/                      # Core functionality
│   │   ├── base_client.py         # Abstract base client class
│   │   ├── mqtt_abstraction.py   # MQTT transport layer
│   │   └── topic_manager.py      # VDA5050 topic management
│   ├── models/                    # Pydantic data models
│   │   ├── base.py               # Base VDA5050 message class
│   │   ├── connection.py         # Connection state messages
│   │   ├── factsheet.py          # AGV capability messages
│   │   ├── instant_action.py     # Instant action messages
│   │   ├── order.py              # Order/navigation messages
│   │   ├── state.py              # AGV state messages
│   │   └── visualization.py      # Visualization messages
│   ├── utils/                     # Utility modules
│   │   └── exceptions.py         # Custom exception classes
│   └── validation/               # Message validation
│       ├── schemas/              # JSON schema files
│       └── validator.py          # Schema validation logic
├── examples/                      # Demo scripts
│   ├── complete_vda5050_demo.py  # Single-script complete demo
│   ├── agv_simulator.py         # AGV simulation example
│   └── master_control.py       # Master control example
├── tests/                         # Test suite
│   ├── integration/              # Integration tests
│   │   └── test_integration_smoke.py
│   └── unit/                     # Unit tests
│       ├── models/              # Model-specific tests
│       ├── test_agv_client.py   # AGV client tests
│       └── test_master_control_client.py
├── pyproject.toml               # Project configuration
└── README.md                    # This documentation
```

### What the library is and the problems it solves

The VDA5050 Python Client Library enables seamless communication between AGVs and master control systems using the VDA5050 standard. It solves the complexity of:

- **Protocol Implementation**: Handles all VDA5050 message types (Connection, Factsheet, State, Order, InstantActions)
- **MQTT Integration**: Manages MQTT broker connections, topic management, and message routing
- **Message Validation**: Ensures all messages comply with VDA5050 JSON schemas
- **Event Handling**: Provides callback-based architecture for reactive programming
- **Connection Management**: Handles AGV online/offline states and retained messages

### Supported VDA5050 version(s) and key features

- **VDA5050 Version**: 2.1.0 (configurable)
- **Key Features**:
  - Full VDA5050 protocol implementation
  - MQTT transport layer with automatic reconnection
  - JSON schema validation for all message types
  - Retained message support for connection state and factsheet
  - Wildcard subscriptions for master control systems
  - Async/await support for modern Python applications
  - Comprehensive error handling and logging

## Requirements

### Python version compatibility

- **Python**: 3.8+ (tested on 3.8, 3.9, 3.10, 3.11, 3.12)

### Main dependencies

- **paho-mqtt**: >=2.0.0, <3.0.0 - MQTT client library
- **pydantic**: >=2.0.0, <3.0.0 - Data validation and serialization
- **jsonschema**: >=4.0.0, <5.0.0 - JSON schema validation

### MQTT broker requirement

- Any MQTT broker compatible with MQTT 3.1.1 (e.g., Mosquitto, HiveMQ, AWS IoT Core)
- Default configuration: `localhost:1883` (no authentication required for development)

## Installation

### Installing from GitHub

```bash
pip install git+https://github.com/zeki-aitech/vda5050_client.git
```

### Installing a specific branch or tag

```bash
# Install from a specific branch
pip install git+https://github.com/zeki-aitech/vda5050_client.git@branch-name

# Install a specific tag/version
pip install git+https://github.com/zeki-aitech/vda5050_client.git@v0.1.0
```

### Development install (editable mode)

```bash
git clone https://github.com/zeki-aitech/vda5050_client.git
cd vda5050_client
pip install -e .
```

## Quick Start Example

```python
import asyncio
from vda5050.clients.agv import AGVClient
from vda5050.clients.master_control import MasterControlClient
from vda5050.models.connection import ConnectionState
from vda5050.models.order import Order, Node, Edge

async def main():
    # AGV Client Setup
    agv = AGVClient(
        broker_url="localhost",
        manufacturer="MyCompany",
        serial_number="AGV001"
    )
    
    # Master Control Client Setup
    master = MasterControlClient(
        broker_url="localhost", 
        manufacturer="MasterControl",
        serial_number="MC001"
    )
    
    # Register callbacks
    def on_order_received(order: Order):
        print(f"AGV received order: {order.orderId}")
    
    agv.on_order_received(on_order_received)
    
    # Connect both clients
    await agv.connect()
    await master.connect()
    
    # Send an order from master to AGV
    order = Order(
        headerId=1,
        timestamp=datetime.now(timezone.utc),
        version="2.1.0",
        manufacturer="MyCompany",
        serialNumber="AGV001",
        orderId="order-001",
        nodes=[Node(nodeId="node1", nodePosition={"x": 0, "y": 0})],
        edges=[]
    )
    
    await master.send_order("MyCompany", "AGV001", order)
    
    # Cleanup
    await agv.disconnect()
    await master.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Usage Guide

### Sending and receiving each message type

#### Connection Messages
```python
# AGV publishes connection state
await agv.update_connection(ConnectionState.ONLINE)
await agv.update_connection(ConnectionState.OFFLINE)

# Master receives connection updates
def on_connection_change(serial: str, state: str):
    print(f"AGV {serial} is now {state}")

master.on_connection_change(on_connection_change)
```

#### Factsheet Messages
```python
# AGV publishes factsheet (retained)
factsheet = Factsheet(
    headerId=0,
    timestamp=datetime.now(timezone.utc),
    version="2.1.0",
    manufacturer="MyCompany",
    serialNumber="AGV001",
    # ... other factsheet fields
)
await agv.send_factsheet(factsheet)

# Master receives factsheet
def on_factsheet_received(serial: str, factsheet: Factsheet):
    print(f"Received factsheet from {serial}")

master.on_factsheet(on_factsheet_received)
```

#### State Messages
```python
# AGV publishes state updates
state = State(
    headerId=1,
    timestamp=datetime.now(timezone.utc),
    version="2.1.0",
    manufacturer="MyCompany",
    serialNumber="AGV001",
    # ... state fields
)
await agv.send_state(state)

# Master receives state updates
def on_state_update(serial: str, state: State):
    print(f"AGV {serial} state: {state.agvPosition}")

master.on_state_update(on_state_update)
```

#### Order Messages
```python
# Master sends order to AGV
order = Order(
    headerId=1,
    timestamp=datetime.now(timezone.utc),
    version="2.1.0",
    manufacturer="MyCompany",
    serialNumber="AGV001",
    orderId="order-001",
    nodes=[Node(nodeId="node1", nodePosition={"x": 0, "y": 0})],
    edges=[]
)
await master.send_order("MyCompany", "AGV001", order)

# AGV receives orders
def on_order_received(order: Order):
    print(f"Received order: {order.orderId}")

agv.on_order_received(on_order_received)
```

#### InstantAction Messages
```python
# Master sends instant action
action = InstantActions(
    headerId=1,
    timestamp=datetime.now(timezone.utc),
    version="2.1.0",
    manufacturer="MyCompany",
    serialNumber="AGV001",
    instantActions=[Action(actionId="stop", actionType="stop")]
)
await master.send_instant_action("MyCompany", "AGV001", action)

# AGV receives instant actions
def on_instant_action(action: InstantActions):
    print(f"Received instant action: {action.instantActions[0].actionType}")

agv.on_instant_action(on_instant_action)
```

### Enabling/disabling schema validation

```python
# Enable validation (default)
agv = AGVClient(
    broker_url="localhost",
    manufacturer="MyCompany", 
    serial_number="AGV001",
    validate_messages=True  # Default
)

# Disable validation for performance
agv = AGVClient(
    broker_url="localhost",
    manufacturer="MyCompany",
    serial_number="AGV001", 
    validate_messages=False
)
```

### Retained messages explanation

Retained messages are automatically used for:
- **Connection state**: AGV connection status (ONLINE/OFFLINE) is retained so new subscribers immediately know the current state
- **Factsheet**: AGV capability information is retained for new master control systems joining the network

```python
# These messages are automatically retained
await agv.update_connection(ConnectionState.ONLINE)  # Retained
await agv.send_factsheet(factsheet)  # Retained

# State updates are not retained (transient)
await agv.send_state(state)  # Not retained
```

## Demo Scripts

### How to run the single-script demo

The complete demo shows the full VDA5050 flow in one script:

```bash
# Start MQTT broker (if not already running)
mosquitto -p 1883

# Run the complete demo
python examples/complete_vda5050_demo.py
```

This demo covers:
- AGV and Master Control client setup
- Connection state management
- Factsheet publication
- State updates
- Order and instant action exchange
- Graceful shutdown

### How to run the separate AGV and Master simulations

#### Terminal 1 - Start MQTT Broker
```bash
mosquitto -p 1883
```

#### Terminal 2 - Run AGV Simulator
```bash
python examples/agv_simulator.py
```

#### Terminal 3 - Run Master Control
```bash
python examples/master_control.py
```

The separate simulations allow you to:
- Test AGV behavior independently
- Test master control functionality
- Simulate multiple AGVs by running multiple AGV simulators
- Debug specific client behavior

## API Reference Overview

### Core classes and methods

#### AGVClient
```python
class AGVClient(VDA5050BaseClient):
    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs)
    async def connect(self) -> bool
    async def disconnect(self)
    async def send_factsheet(self, factsheet: Factsheet) -> bool
    async def send_state(self, state: State) -> bool
    async def update_connection(self, connection_state: ConnectionState) -> bool
    def on_order_received(self, callback: Callable[[Order], None])
    def on_instant_action(self, callback: Callable[[InstantActions], None])
```

#### MasterControlClient
```python
class MasterControlClient(VDA5050BaseClient):
    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs)
    async def connect(self) -> bool
    async def disconnect(self)
    async def send_order(self, target_manufacturer: str, target_serial: str, order: Order) -> bool
    async def send_instant_action(self, target_manufacturer: str, target_serial: str, action: InstantActions) -> bool
    def on_state_update(self, callback: Callable[[str, State], None])
    def on_connection_change(self, callback: Callable[[str, str], None])
    def on_factsheet(self, callback: Callable[[str, Factsheet], None])
```

#### VDA5050BaseClient
```python
class VDA5050BaseClient(ABC):
    def __init__(self, manufacturer: str, serial_number: str, broker_url: str, **kwargs)
    async def connect(self) -> bool
    async def disconnect(self)
    def is_connected(self) -> bool
    def register_handler(self, message_type: str, handler: Callable, **kwargs)
```

### Key Pydantic models with field summaries

#### VDA5050Message (Base)
- `headerId`: Unique message identifier
- `timestamp`: ISO8601 timestamp
- `version`: VDA5050 protocol version
- `manufacturer`: AGV manufacturer name
- `serialNumber`: AGV serial number

#### Connection
- `connectionState`: ONLINE/OFFLINE status

#### Factsheet
- `agvClass`: AGV classification
- `physicalParameters`: Physical specifications
- `protocolLimits`: Communication limits
- `protocolFeatures`: Supported features

#### State
- `agvPosition`: Current position and orientation
- `velocity`: Current velocity
- `batteryState`: Battery information
- `safetyState`: Safety status
- `operatingMode`: Current operating mode

#### Order
- `orderId`: Unique order identifier
- `nodes`: Navigation nodes
- `edges`: Navigation edges
- `zoneSetId`: Zone restrictions

#### InstantActions
- `instantActions`: List of immediate actions
- `blockingType`: Action blocking behavior

## Integration Testing

### How to run the integration smoke test

The integration test validates the complete VDA5050 message flow:

```bash
# Run all tests
pytest tests/

# Run only integration tests
pytest tests/integration/

# Run with verbose output
pytest tests/integration/test_integration_smoke.py -v
```


## Configuration

### Customizing broker URL/port
```python
agv = AGVClient(
    broker_url="mqtt.example.com",
    broker_port=8883,  # SSL port
    manufacturer="MyCompany",
    serial_number="AGV001"
)
```

### Client identity
```python
agv = AGVClient(
    broker_url="localhost",
    manufacturer="MyCompany",  # Must match VDA5050 identity
    serial_number="AGV001"     # Must be unique per manufacturer
)
```

### Validation flags
```python
agv = AGVClient(
    broker_url="localhost",
    manufacturer="MyCompany",
    serial_number="AGV001",
    validate_messages=True,  # Enable/disable schema validation
    interface_name="uagv",   # VDA5050 interface name
    version="2.1.0"         # VDA5050 protocol version
)
```

### Retain behavior
```python
# Connection and factsheet are automatically retained
await agv.update_connection(ConnectionState.ONLINE)  # Retained=True
await agv.send_factsheet(factsheet)  # Retained=True

# State updates are not retained (transient)
await agv.send_state(state)  # Retained=False
```



## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.

---

For more information, visit the [VDA5050 specification](https://github.com/VDA5050/VDA5050) and the [project repository](https://github.com/zeki-aitech/vda5050_client).