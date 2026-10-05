"""
The asyncio clients against a real broker that is restarted (finding T1 of
the 0.1.2 audit): after the connection came back, orders, instant actions
and states must flow again, and ONLINE must be on the broker again.

Written against the public asyncio API of 0.1.2, which 0.2.0 keeps.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from vda5050.clients.agv import AGVClient
from vda5050.clients.master_control import MasterControlClient
from vda5050.models import InstantActions, Order, State

from .mqtt_broker import retained

pytestmark = pytest.mark.asyncio

MANUFACTURER = "TestMan"
SERIAL = "r1"


def make_order(n: int) -> Order:
    return Order.model_validate({
        "headerId": n, "timestamp": datetime.now(timezone.utc), "version": "2.1.0",
        "manufacturer": MANUFACTURER, "serialNumber": SERIAL,
        "orderId": f"o{n}", "orderUpdateId": 0,
        "nodes": [{"nodeId": "n1", "sequenceId": 0, "released": True, "actions": [],
                   "nodePosition": {"x": 1.0, "y": 2.0, "mapId": "map"}}],
        "edges": [],
    })


def make_instant(n: int) -> InstantActions:
    return InstantActions.model_validate({
        "headerId": n, "timestamp": datetime.now(timezone.utc), "version": "2.1.0",
        "manufacturer": MANUFACTURER, "serialNumber": SERIAL,
        "actions": [{"actionType": "startPause", "actionId": f"a{n}", "blockingType": "HARD"}],
    })


def make_state(n: int) -> State:
    return State.model_validate({
        "headerId": n, "timestamp": datetime.now(timezone.utc), "version": "2.1.0",
        "manufacturer": MANUFACTURER, "serialNumber": SERIAL,
        "orderId": "", "orderUpdateId": 0, "lastNodeId": "", "lastNodeSequenceId": 0,
        "nodeStates": [], "edgeStates": [], "driving": False, "actionStates": [],
        "batteryState": {"batteryCharge": 50.0, "charging": False},
        "operatingMode": "AUTOMATIC", "errors": [],
        "safetyState": {"eStop": "NONE", "fieldViolation": False},
    })


async def eventually(predicate, timeout: float) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.05)
    return predicate()


async def exchange(agv, mc, n, orders, actions, states) -> bool:
    """One order and one instant action to the AGV, one state to the master."""
    o, a, s = len(orders), len(actions), len(states)
    await mc.send_order(MANUFACTURER, SERIAL, make_order(n))
    await mc.send_instant_action(MANUFACTURER, SERIAL, make_instant(n))
    await agv.send_state(make_state(n))
    return await eventually(
        lambda: len(orders) > o and len(actions) > a and len(states) > s, timeout=5
    )


async def test_messages_flow_again_after_broker_restart(broker):
    orders, actions, states = [], [], []
    agv = AGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=broker.port)
    mc = MasterControlClient("127.0.0.1", MANUFACTURER, "master", broker_port=broker.port)
    agv.on_order_received(lambda o: orders.append(o.orderId))
    agv.on_instant_action(lambda a: actions.append(a.actions[0].actionId))
    mc.on_state_update(lambda serial, st: states.append(serial))
    try:
        assert await agv.connect()
        assert await mc.connect()
        await asyncio.sleep(0.3)
        # Positive control: the exchange works before the restart.
        assert await exchange(agv, mc, 1, orders, actions, states)

        await asyncio.get_running_loop().run_in_executor(None, broker.restart)

        # is_connected() must tell the truth; mqtt._state is what the screen reads.
        assert await eventually(
            lambda: agv.is_connected() and mc.is_connected()
            and agv.mqtt._state.name == "CONNECTED" and mc.mqtt._state.name == "CONNECTED",
            timeout=20,
        )
        await asyncio.sleep(0.5)
        assert await exchange(agv, mc, 2, orders, actions, states), (
            f"after the restart: orders {orders}, actions {actions}, states {states}"
        )
        msg = await asyncio.get_running_loop().run_in_executor(
            None, retained, broker.port, f"uagv/v2/{MANUFACTURER}/{SERIAL}/connection"
        )
        assert msg is not None and b'"ONLINE"' in msg.payload
    finally:
        await agv.disconnect()
        await mc.disconnect()
