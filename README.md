# VDA5050 Python Client Library

A comprehensive Python client library for implementing VDA5050 AGV (Automated Guided Vehicle) communication protocol. This library provides both AGV and Master Control clients with full MQTT integration, message validation, and callback-based event handling.

## Project Overview

### Project Structure

```
vda5050_client/
├── src/vda5050/                    # Main library source code
│   ├── clients/                    # Client implementations
│   │   ├── threaded.py            # AGV and master control clients, no asyncio
│   │   ├── agv.py                 # AGV client for asyncio (over threaded.py)
│   │   └── master_control.py      # Master control client for asyncio (over threaded.py)
│   ├── core/                      # Core functionality
│   │   ├── transport.py           # MQTT on paho's thread: reconnects, resubscribes
│   │   ├── threaded_client.py     # VDA5050 rules: QoS, retain, header, checks on receive
│   │   ├── base_client.py         # asyncio layer: callbacks onto the event loop
│   │   ├── mqtt_abstraction.py    # ConnectionState, kept for 0.1.x imports
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
│       ├── schemas/              # JSON schemas used to validate (2.1.0, corrected)
│       │   └── official-2.1.0/   # the official schemas, unchanged, for comparison
│       └── validator.py          # Schema validation logic
├── examples/                      # Demo scripts
│   ├── complete_vda5050_demo.py  # Single-script complete demo
│   ├── agv_simulator.py         # AGV simulation example
│   └── master_control.py       # Master control example
├── tests/                         # Test suite
│   ├── broker/                   # Against a real mosquitto the tests start
│   │   ├── test_threaded.py     # (re)connection, last will, QoS, header, checks
│   │   ├── test_async.py        # the asyncio clients, as applications use them
│   │   └── test_integration_smoke.py
│   └── unit/                     # Unit tests
│       ├── models/              # Model-specific tests
│       ├── test_conformance.py  # models and schemas against the official 2.1.0
│       └── test_threaded_client.py
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
  - Connects whether or not the broker is up at start, and reconnects for
    ever: subscriptions made again, `ONLINE` and the factsheet published
    again, after every reconnection
  - MQTT rules of VDA5050 6.2 and 6.14: QoS 0 for `order`, `instantActions`,
    `state`, `factsheet`, `visualization`, QoS 1 for `connection`;
    `connection` and `factsheet` retained; `CONNECTIONBROKEN` as last will
  - The header written by the library: `headerId` counted per topic,
    timestamps in UTC with `Z`
  - JSON schema validation for all message types; a message that fails is
    handed to the application with the reason
  - Clients that need no asyncio (`ThreadedAGVClient`,
    `ThreadedMasterControlClient`), and the same for asyncio (`AGVClient`,
    `MasterControlClient`)

## Requirements

### Python version compatibility

- **Python**: 3.10+ (tested in CI on 3.10 and 3.13). 0.1.x said 3.8+, but
  its validator did not import on 3.8 or 3.9.

### Main dependencies

- **paho-mqtt**: >=2.0.0, <3.0.0 - MQTT client library
- **pydantic**: >=2.0.0, <3.0.0 - Data validation and serialization
- **jsonschema**: >=4.0.0, <5.0.0 - JSON schema validation

### MQTT broker requirement

- Any MQTT broker compatible with MQTT 3.1.1 (e.g., Mosquitto, HiveMQ, AWS IoT Core)
- Default configuration: `localhost:1883` (no authentication required for development)
- The tests need the `mosquitto` binary; they start their own brokers on
  free ports of 127.0.0.1 and never use one already running

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
pip install git+https://github.com/zeki-aitech/vda5050_client.git@v0.2.0
```

### Development install (editable mode)

```bash
git clone https://github.com/zeki-aitech/vda5050_client.git
cd vda5050_client
pip install -e .
```

## What changed in 0.2.0, and how to move from 0.1.2

0.2.0 corrects the transport against VDA5050 2.1.0 (sections 6.2, 6.4,
6.6.4.1, 6.14). The public asyncio API of 0.1.2 is kept: an application
written for 0.1.2 runs unchanged. What it will notice:

| | 0.1.2 | 0.2.0 |
|---|---|---|
| After the broker was lost and came back | reconnected, but subscribed to nothing and did not publish `ONLINE` again: nothing was received any more | subscriptions made again, `ONLINE` and the last factsheet published again, on every reconnection |
| Broker not reachable at `connect()` | `False`, and never tried again | `False` after the first attempt (at most `timeout`, 10 s), and the client goes on trying, with back-off (1 s doubling to 30 s), until `disconnect()` |
| `is_connected()` | true from `connect()` to `disconnect()`, whatever the link | the MQTT connection as it is now |
| QoS | 1 for everything; each publish waited for its acknowledgement (up to 10 s) | 1 for `connection`, 0 for the others; a publish never waits |
| Publishing while disconnected | `False` (raised inside) | `False`; the message is dropped, not kept for later |
| `headerId` | whatever the caller put in | counted by the library per topic, from 0, +1 per message sent, back to 0 after 2^32 - 1; the caller's value is ignored |
| `timestamp` | written as given | converted to UTC and written with `Z`; a time without a time zone is refused (`ValidationError`), because Python's naive times are local times |
| A received message that is not JSON or fails the schema or the model | logged and dropped | handed to `on_invalid_message()` callbacks as an `InvalidMessage` (topic, message type, kind, reason, payload), and logged |
| Received `factsheet` or `visualization` without header fields | refused | accepted, as the official schema allows; on send the client fills them in |
| Keepalive | 60 s | 15 s (VDA5050 6.14: "around 15 seconds") |
| Schema validation | about 50 ms per `state` on an ARM board (the schema itself was checked on every call) | about 0.2 ms (compiled once) |
| Python | said 3.8+ | 3.10+ |

New:

- `ThreadedAGVClient` and `ThreadedMasterControlClient`: the same clients
  without asyncio (below). `AGVClient` and `MasterControlClient` are now a
  thin layer over them; `client.client` is the threaded client.
- `on_broker_connection(callback)`: called with `True` after each
  (re)connection, `False` when it is lost.
- `on_invalid_message(callback)`, `InvalidMessage`.
- `send_visualization()` on the AGV side, `on_visualization()` on the
  master side.

Removed: the asyncio `MQTTAbstraction` class. `client.mqtt` is now an
`MQTTTransport`; its `_state` still holds a `ConnectionState`, still
importable from `vda5050.core.mqtt_abstraction`, with the same four values
(`CONNECTING` before the first connection, `RECONNECTING` after a loss).

Moving from 0.1.2: change the pin to `v0.2.0`. Then check whether the
application counts on any of these:

- it numbers `headerId` itself: the numbers on the wire are now the
  library's;
- it passes naive datetimes as `timestamp`: give `datetime.now(timezone.utc)`;
- it treats a `False` from `connect()` as final, or keeps its own
  "connected" flag from that return value: the client connects later by
  itself, so read `is_connected()` or use `on_broker_connection()`;
- it relies on QoS 1 delivery of orders or states: the standard says QoS 0.

## Clients without asyncio

`ThreadedAGVClient` and `ThreadedMasterControlClient` run on paho's own
network thread. `start()` and every `send_*()` return at once; callbacks run
on the network thread, one at a time, in arrival order. An application with
its own executor (a ROS node, a GUI) should only queue the message there.

```python
from datetime import datetime, timezone
from vda5050 import ThreadedAGVClient

agv = ThreadedAGVClient("localhost", "MyCompany", "AGV001")
agv.on_order_received(lambda order: queue.put(order))        # network thread
agv.on_instant_action(lambda actions: queue.put(actions))
agv.on_invalid_message(lambda bad: queue.put(bad))           # e.g. to report a validationError
agv.on_broker_connection(lambda up: print("broker", "up" if up else "down"))
agv.send_factsheet(factsheet)   # kept; published on every (re)connection

agv.start()                     # connects when the broker answers; reconnects until stop()
...
if not agv.send_state(state):   # never blocks
    pass                        # not connected: this state is dropped
...
agv.stop()                      # OFFLINE, then a clean disconnect (no last will)
```

`ThreadedMasterControlClient` has `send_order(manufacturer, serial, order)`,
`send_instant_action(...)`, and the callbacks `on_state_update`,
`on_connection_change`, `on_factsheet` and `on_visualization`, each called
with `(serial_number, message)`. Both have `is_connected()`,
`wait_connected(timeout)`, `on_broker_connection()` and
`on_invalid_message()`. Options: `client_id`, `keepalive` (15),
`reconnect_min_delay` (1), `reconnect_max_delay` (30); TLS and other paho
settings go on `client.transport.paho` before `start()`.

## The bundled schemas: where they come from

Messages are validated against the schemas in
`src/vda5050/validation/schemas/`. They are the official VDA5050 **2.1.0**
schemas (https://github.com/VDA5050/VDA5050, tag `2.1.0`) with these
corrections, each one following the specification's text where the 2.1.0
schema departs from it:

| Schema | Correction | Why |
|---|---|---|
| `state` | `actionStates[].actionStatus` has `PAUSED` | in the text; missing from the 2.1.0 schema, corrected upstream on 2025-02-20 |
| `factsheet` | `agvActions[].blockingTypes` is an array of the enum | the 2.1.0 schema put the enum on the array; corrected upstream the same day |
| `factsheet` | `agvGeometry.envelopes3d[].description` is a string | the text says string; the 2.1.0 schema says integer |
| `order` | `nodePosition.allowedDeviationTheta` minimum 0 | the text gives the range [0, pi]; the 2.1.0 schema has minimum -pi |

The pydantic models carry the same corrections, and also: trajectory
`degree` minimum 1 and control point `weight` minimum 0 (as the text), and
`mapDescription` accepted in the position of `visualization` (it is the
position object of `state`).

The official schemas are kept unchanged beside the bundled ones, in
`schemas/official-2.1.0/` (with their MIT licence). `tests/unit/test_conformance.py`
compares the models and the bundled schemas with them, field by field, and
fails on any difference not listed above.

## Quick Start Example

```python
import asyncio
from datetime import datetime, timezone
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
    async def connect(self, timeout: float = 10.0) -> bool  # keeps trying if False
    async def disconnect(self)
    def is_connected(self) -> bool                          # the MQTT connection now
    def register_handler(self, message_type: str, handler: Callable, **kwargs)
    def on_broker_connection(self, callback: Callable[[bool], None])
    def on_invalid_message(self, callback: Callable[[InvalidMessage], None])
```

AGVClient also has `send_visualization()`; MasterControlClient also has
`on_visualization()`.

#### ThreadedAGVClient, ThreadedMasterControlClient
```python
class ThreadedAGVClient:
    def __init__(self, broker_url: str, manufacturer: str, serial_number: str, **kwargs)
    def start(self)                              # returns at once
    def stop(self)
    def is_connected(self) -> bool
    def wait_connected(self, timeout=None) -> bool
    def send_state(self, state: State) -> bool   # never blocks
    def send_visualization(self, visualization: Visualization) -> bool
    def send_factsheet(self, factsheet: Factsheet) -> bool
    def update_connection(self, connection_state: ConnectionState) -> bool
    def on_order_received(self, callback: Callable[[Order], None])
    def on_instant_action(self, callback: Callable[[InstantActions], None])
    def on_broker_connection(self, callback: Callable[[bool], None])
    def on_invalid_message(self, callback: Callable[[InvalidMessage], None])

class ThreadedMasterControlClient:
    # start, stop, is_connected, wait_connected, on_broker_connection,
    # on_invalid_message as above, and:
    def send_order(self, target_manufacturer: str, target_serial: str, order: Order) -> bool
    def send_instant_action(self, target_manufacturer: str, target_serial: str, action: InstantActions) -> bool
    def on_state_update(self, callback: Callable[[str, State], None])
    def on_connection_change(self, callback: Callable[[str, str], None])
    def on_factsheet(self, callback: Callable[[str, Factsheet], None])
    def on_visualization(self, callback: Callable[[str, Visualization], None])
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

The tests in `tests/broker/` start their own mosquitto (the `mosquitto`
binary must be installed; without it they are skipped, unless
`VDA5050_REQUIRE_BROKER=1`, as in CI, which makes them fail). They cover the
broker absent at start, a broker restart, the last will after a killed
client, QoS and retain on the wire, the header, and invalid messages.

```bash
uv sync
uv run pytest tests/                 # everything
uv run pytest tests/broker/ -v       # only what needs a broker
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

### Retain and QoS
```python
# Connection and factsheet are retained; connection is QoS 1, the rest QoS 0
await agv.update_connection(ConnectionState.ONLINE)  # retained, QoS 1
await agv.send_factsheet(factsheet)  # retained, QoS 0

# State updates are not retained (transient)
await agv.send_state(state)  # not retained, QoS 0
```



## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE.txt) file for details.

---

For more information, visit the [VDA5050 specification](https://github.com/VDA5050/VDA5050) and the [project repository](https://github.com/zeki-aitech/vda5050_client).