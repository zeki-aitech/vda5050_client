"""
The asyncio clients against a real broker, used the way their two
applications use them (the mission bridge: AGVClient; the operator screen:
MasterControlClient, reading client.mqtt._state). Written against the
public asyncio API of 0.1.2, which 0.2.0 keeps.

The first test is finding T1 of the 0.1.2 audit: after the broker was
restarted, orders, instant actions and states must flow again, and ONLINE
must be on the broker again.
"""

import asyncio
import threading

import pytest

from vda5050.clients.agv import AGVClient
from vda5050.clients.master_control import MasterControlClient
from vda5050.core.mqtt_abstraction import ConnectionState as MQTTState
from vda5050.models.connection import ConnectionState
from vda5050.utils.exceptions import VDA5050Error

from .messages import MANUFACTURER, SERIAL, make_factsheet, make_instant, make_order, make_state
from .mqtt_broker import retained

pytestmark = pytest.mark.asyncio

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


def connection_states(observer):
    import json
    return [json.loads(m.payload)["connectionState"] for m in observer.on("/connection")]


async def test_bridge_usage(broker, observer):
    """What the mission bridge (0.1.x) does with AGVClient, in its order."""
    agv = AGVClient(
        broker_url="127.0.0.1", manufacturer=MANUFACTURER, serial_number=SERIAL,
        broker_port=broker.port, interface_name="uagv", version="2.0",
        validate_messages=True, username=None, password=None,
    )
    orders, actions, threads = [], [], set()
    agv.on_order_received(lambda o: (orders.append(o.orderId), threads.add(threading.get_ident())))
    agv.on_instant_action(lambda a: actions.append(a))
    mc = MasterControlClient("127.0.0.1", MANUFACTURER, "master", broker_port=broker.port)
    try:
        assert await agv.connect() is True
        assert await agv.update_connection(ConnectionState.ONLINE) is True
        assert await agv.send_factsheet(make_factsheet(1)) is True
        assert await agv.send_state(make_state(5)) is True
        assert await mc.connect()
        await asyncio.sleep(0.2)
        await mc.send_order(MANUFACTURER, SERIAL, make_order(1))
        await mc.send_instant_action(MANUFACTURER, SERIAL, make_instant(1))
        assert await eventually(lambda: orders == ["o1"] and len(actions) == 1, 5)
        assert threads == {threading.get_ident()}, "callbacks run on the loop's thread"
    finally:
        await agv.disconnect()
        await mc.disconnect()
    assert not agv.is_connected()
    assert connection_states(observer) == ["ONLINE", "ONLINE", "OFFLINE"]


async def test_bridge_start_without_broker(broker):
    """connect() comes back quickly with False, and the client keeps trying."""
    broker.stop()
    agv = AGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=broker.port)
    orders = []
    agv.on_order_received(lambda o: orders.append(o.orderId))
    try:
        t0 = asyncio.get_running_loop().time()
        assert await agv.connect() is False
        assert asyncio.get_running_loop().time() - t0 < 3
        with pytest.raises(VDA5050Error):
            await agv.update_connection(ConnectionState.ONLINE)
        assert await agv.send_state(make_state()) is False
        await asyncio.get_running_loop().run_in_executor(None, broker.start)
        assert await eventually(agv.is_connected, 15)
        mc = MasterControlClient("127.0.0.1", MANUFACTURER, "master", broker_port=broker.port)
        assert await mc.connect()
        try:
            await asyncio.sleep(0.2)
            await mc.send_order(MANUFACTURER, SERIAL, make_order(1))
            assert await eventually(lambda: orders == ["o1"], 5)
        finally:
            await mc.disconnect()
    finally:
        await agv.disconnect()


async def test_screen_usage(broker):
    """What the operator screen (0.1.x) does with MasterControlClient."""
    mc = MasterControlClient("127.0.0.1", "TestMan", "gui-master-r1",
                             broker_port=broker.port, validate_messages=False)
    agv = AGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=broker.port)
    states, links = [], []
    mc.on_state_update(lambda serial, st: states.append(serial))
    mc.on_connection_change(lambda serial, c: links.append((serial, c)))
    try:
        assert await mc.connect()
        assert mc.mqtt._state == MQTTState.CONNECTED
        assert await agv.connect()
        assert await eventually(lambda: (SERIAL, "ONLINE") in links, 5)
        await agv.send_state(make_state())
        assert await eventually(lambda: states == [SERIAL], 5)

        # The screen polls client.mqtt._state; while the broker is away the
        # state is neither CONNECTED nor DISCONNECTED (the screen calls
        # connect() again only on DISCONNECTED).
        await asyncio.get_running_loop().run_in_executor(None, broker.stop)
        assert await eventually(lambda: mc.mqtt._state == MQTTState.RECONNECTING, 5)
        assert not mc.is_connected()
        await asyncio.get_running_loop().run_in_executor(None, broker.start)
        assert await eventually(lambda: mc.mqtt._state == MQTTState.CONNECTED, 15)

        # disconnect_broker() then connect_broker()
        await mc.disconnect()
        assert mc.mqtt._state == MQTTState.DISCONNECTED and not mc.is_connected()
        assert await mc.connect()
        assert await eventually(agv.is_connected, 15)
        n = len(states)
        await agv.send_state(make_state())
        assert await eventually(lambda: len(states) > n, 5)
    finally:
        await agv.disconnect()
        await mc.disconnect()


async def test_one_processing_task(broker):
    mc = MasterControlClient("127.0.0.1", "TestMan", "master", broker_port=broker.port)

    def processors():
        return [t for t in asyncio.all_tasks()
                if t.get_coro().__qualname__.endswith("VDA5050BaseClient._process")]
    try:
        for _ in range(3):
            assert await mc.connect()
            await asyncio.get_running_loop().run_in_executor(None, broker.restart, 0.2)
            assert await eventually(mc.is_connected, 15)
        assert len(processors()) == 1
    finally:
        await mc.disconnect()
    assert processors() == []


async def test_raw_handler_and_invalid_messages_on_the_loop(broker):
    agv = AGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=broker.port)
    raw, invalid, links = [], [], []

    async def on_raw(topic, payload):
        raw.append((topic, payload))

    agv.register_handler("order", on_raw)
    agv.on_invalid_message(invalid.append)
    agv.on_broker_connection(links.append)
    mc = MasterControlClient("127.0.0.1", MANUFACTURER, "master", broker_port=broker.port)
    try:
        assert await agv.connect() and await mc.connect()
        await asyncio.sleep(0.2)
        await mc.send_order(MANUFACTURER, SERIAL, make_order(1))
        import paho.mqtt.publish as publish
        publish.single(f"uagv/v2/{MANUFACTURER}/{SERIAL}/order", "nope",
                       hostname="127.0.0.1", port=broker.port)
        assert await eventually(lambda: len(raw) == 1 and len(invalid) == 1, 5)
        assert raw[0][0].endswith("/order") and '"orderId":"o1"' in raw[0][1]
        assert invalid[0].kind == "json" and invalid[0].message_type == "order"
        assert links == [True]
    finally:
        await agv.disconnect()
        await mc.disconnect()
