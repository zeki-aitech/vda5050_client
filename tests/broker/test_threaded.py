"""
The threaded clients against a real mosquitto: connection and reconnection
(L1), QoS and retain on the wire (L2), the header (L3), messages that are
not delivered (L4), factsheet and visualization without header (L8), and
the callbacks' single thread (L7).
"""

import json
import signal
import subprocess
import sys
import textwrap
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from vda5050 import (
    InvalidMessage,
    MQTTConnectionState,
    ThreadedAGVClient,
    ThreadedMasterControlClient,
)
from vda5050.models.connection import ConnectionState
from vda5050.utils.exceptions import ValidationError

from .messages import (
    FACTSHEET_BODY,
    MANUFACTURER,
    SERIAL,
    make_factsheet,
    make_instant,
    make_order,
    make_state,
    make_visualization,
)
from .mqtt_broker import Observer, retained, wait_until

BASE = f"uagv/v2/{MANUFACTURER}/{SERIAL}"
SRC = str(Path(__file__).resolve().parents[2] / "src")


class Recorder:
    """Collects what the callbacks of a client deliver, and on which thread."""

    def __init__(self):
        self.items = []
        self.threads = set()
        self._lock = threading.Lock()

    def __call__(self, *args):
        with self._lock:
            self.items.append(args if len(args) > 1 else args[0])
            self.threads.add(threading.current_thread().name)

    def __len__(self):
        with self._lock:
            return len(self.items)


@pytest.fixture
def agv(broker):
    c = ThreadedAGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=broker.port)
    yield c
    c.stop()


@pytest.fixture
def master(broker):
    c = ThreadedMasterControlClient("127.0.0.1", MANUFACTURER, "master", broker_port=broker.port)
    yield c
    c.stop()


def payload(msg) -> dict:
    return json.loads(msg.payload)


# ── L1: connection and reconnection ───────────────────────────────


def test_broker_absent_at_start_then_appears(broker, agv, master):
    broker.stop()
    links = Recorder()
    orders = Recorder()
    agv.on_broker_connection(links)
    agv.on_order_received(orders)

    t0 = time.monotonic()
    agv.start()
    master.start()
    assert time.monotonic() - t0 < 1.0, "start() must not block"
    assert agv.transport.wait_first_attempt(5) is False
    assert not agv.is_connected()
    assert agv.transport._state is MQTTConnectionState.CONNECTING
    time.sleep(2.5)  # several attempts fail, with back-off

    broker.start()
    assert agv.wait_connected(15) and master.wait_connected(15)
    assert links.items == [True]
    msg = retained(broker.port, f"{BASE}/connection")
    assert msg is not None and payload(msg)["connectionState"] == "ONLINE"
    assert wait_until(lambda: master.send_order(MANUFACTURER, SERIAL, make_order(1))
                      and len(orders) >= 1, timeout=5)


def test_broker_restart_subscribes_and_announces_again(broker, observer, agv, master):
    links = Recorder()
    orders, actions, states = Recorder(), Recorder(), Recorder()
    agv.on_broker_connection(links)
    agv.on_order_received(orders)
    agv.on_instant_action(actions)
    master.on_state_update(states)
    agv.send_factsheet(make_factsheet())  # not connected yet: kept, sent on connection
    agv.start()
    master.start()
    assert agv.wait_connected(5) and master.wait_connected(5)

    def exchange():
        o, a, s = len(orders), len(actions), len(states)
        master.send_order(MANUFACTURER, SERIAL, make_order(1))
        master.send_instant_action(MANUFACTURER, SERIAL, make_instant(1))
        agv.send_state(make_state())
        return wait_until(lambda: len(orders) > o and len(actions) > a and len(states) > s, 5)

    assert wait_until(lambda: observer.on("/factsheet"), 5)
    assert exchange()
    observer.close()

    broker.stop()
    assert wait_until(lambda: not agv.is_connected() and not master.is_connected(), 5), \
        "is_connected() must turn false when the broker goes away"
    assert agv.transport._state is MQTTConnectionState.RECONNECTING
    assert agv.send_state(make_state()) is False  # dropped, not raised
    broker.start()
    observer2 = Observer(broker.port)
    try:
        assert agv.wait_connected(15) and master.wait_connected(15)
        assert links.items == [True, False, True]
        assert exchange(), "subscriptions must be made again after a reconnection"
        assert wait_until(lambda: observer2.on("/factsheet"), 5), "factsheet published again"
        online = [payload(m) for m in observer2.on("/connection")]
        assert [p["connectionState"] for p in online] == ["ONLINE"]
        # will = 0, first ONLINE = 1, ONLINE after the restart = 2
        assert online[0]["headerId"] == 2
    finally:
        observer2.close()


def test_last_will_after_killed_client(broker, tmp_path):
    script = tmp_path / "agv.py"
    script.write_text(textwrap.dedent(f"""
        import sys, time
        sys.path.insert(0, {SRC!r})
        from vda5050 import ThreadedAGVClient
        c = ThreadedAGVClient("127.0.0.1", {MANUFACTURER!r}, {SERIAL!r}, broker_port={broker.port})
        c.start()
        assert c.wait_connected(10)
        print("connected", flush=True)
        time.sleep(60)
    """))
    proc = subprocess.Popen([sys.executable, str(script)], stdout=subprocess.PIPE, text=True)
    try:
        assert proc.stdout.readline().strip() == "connected"
        assert wait_until(lambda: (m := retained(broker.port, f"{BASE}/connection", 0.5))
                          and payload(m)["connectionState"] == "ONLINE", 5)
        proc.send_signal(signal.SIGKILL)
        proc.wait(5)
        msg = None

        def broken():
            nonlocal msg
            msg = retained(broker.port, f"{BASE}/connection", 0.5)
            return msg is not None and payload(msg)["connectionState"] == "CONNECTIONBROKEN"

        assert wait_until(broken, 10)
        assert msg.qos == 1 and msg.retain
        assert payload(msg)["headerId"] == 0  # armed before the first ONLINE
    finally:
        proc.kill()


def test_clean_stop_leaves_offline_not_the_will(broker, observer, agv):
    agv.start()
    assert agv.wait_connected(5)
    agv.stop()
    assert not agv.is_connected()
    assert agv.transport._state is MQTTConnectionState.DISCONNECTED
    time.sleep(0.5)
    states = [payload(m)["connectionState"] for m in observer.on("/connection")]
    assert states == ["ONLINE", "OFFLINE"]
    assert payload(retained(broker.port, f"{BASE}/connection"))["connectionState"] == "OFFLINE"


def test_stop_while_broker_absent_ends_the_retries(broker, agv):
    broker.stop()
    agv.start()
    assert agv.transport.wait_first_attempt(5) is False
    t0 = time.monotonic()
    agv.stop()
    assert time.monotonic() - t0 < 5
    broker.start()
    time.sleep(2.5)
    assert not agv.is_connected()


def test_restart_after_stop(broker, agv, master):
    orders = Recorder()
    agv.on_order_received(orders)
    agv.start()
    assert agv.wait_connected(5)
    agv.stop()
    agv.start()
    master.start()
    assert agv.wait_connected(5) and master.wait_connected(5)
    assert wait_until(lambda: master.send_order(MANUFACTURER, SERIAL, make_order(1))
                      and len(orders) >= 1, 5)


# ── L2: QoS and retain on the wire ────────────────────────────────


def test_qos_and_retain_by_topic(broker, observer, agv, master):
    agv.start()
    master.start()
    assert agv.wait_connected(5) and master.wait_connected(5)
    assert agv.send_factsheet(make_factsheet())
    assert agv.send_state(make_state())
    assert agv.send_visualization(make_visualization())
    assert master.send_order(MANUFACTURER, SERIAL, make_order(1))
    assert master.send_instant_action(MANUFACTURER, SERIAL, make_instant(1))
    expected = {"connection": 1, "factsheet": 0, "state": 0, "visualization": 0,
                "order": 0, "instantActions": 0}
    assert wait_until(lambda: all(observer.on(f"/{t}") for t in expected), 5)
    for topic, qos in expected.items():
        assert {m.qos for m in observer.on(f"/{topic}")} == {qos}, topic
    # Retained on the broker: connection and factsheet only.
    for topic in expected:
        held = retained(broker.port, f"{BASE}/{topic}", timeout=0.5)
        assert (held is not None) == (topic in ("connection", "factsheet")), topic
    assert retained(broker.port, f"{BASE}/factsheet").qos == 0


def test_subscriptions_use_the_qos_of_the_standard(agv, master):
    subs = {**agv.transport._subscriptions, **master.transport._subscriptions}
    assert subs == {
        f"{BASE}/order": 0,
        f"{BASE}/instantActions": 0,
        "uagv/v2/+/+/state": 0,
        "uagv/v2/+/+/factsheet": 0,
        "uagv/v2/+/+/connection": 1,
    }


def test_publish_does_not_wait_for_an_acknowledgement(broker, agv):
    agv.start()
    assert agv.wait_connected(5)
    t0 = time.monotonic()
    for _ in range(200):
        assert agv.send_state(make_state())
    assert time.monotonic() - t0 < 1.0


def test_state_while_disconnected_is_dropped_not_queued(broker, observer, agv):
    agv.start()
    assert agv.wait_connected(5)
    observer.close()
    broker.stop()
    assert wait_until(lambda: not agv.is_connected(), 5)
    assert agv.send_state(make_state()) is False
    broker.start()
    o2 = Observer(broker.port)
    try:
        assert agv.wait_connected(15)
        time.sleep(1.0)
        assert o2.on("/state") == []
    finally:
        o2.close()


# ── L3: header ────────────────────────────────────────────────────


def test_header_id_counted_per_topic(broker, observer, agv, master):
    agv.start()
    master.start()
    assert agv.wait_connected(5) and master.wait_connected(5)
    for _ in range(3):
        assert agv.send_state(make_state(n=4711))  # the caller's headerId is replaced
    master.send_order(MANUFACTURER, SERIAL, make_order(99))
    master.send_order(MANUFACTURER, "r2", make_order(99, serial="r2"))
    master.send_order(MANUFACTURER, SERIAL, make_order(99))
    assert wait_until(
        lambda: len(observer.on("/state")) == 3 and len(observer.on("/order")) == 3, 5)
    assert [payload(m)["headerId"] for m in observer.on("/state")] == [0, 1, 2]
    by_topic = {}
    for m in observer.on("/order"):
        by_topic.setdefault(m.topic, []).append(payload(m)["headerId"])
    assert by_topic == {f"{BASE}/order": [0, 1], f"uagv/v2/{MANUFACTURER}/r2/order": [0]}
    # will 0, ONLINE 1: the connection topic has its own counter
    assert [payload(m)["headerId"] for m in observer.on("/connection")] == [1]


def test_header_id_wraps_as_uint32(broker, observer, agv):
    agv.start()
    assert agv.wait_connected(5)
    agv._next_header_id[f"{BASE}/state"] = 2 ** 32 - 1
    agv.send_state(make_state())
    agv.send_state(make_state())
    assert wait_until(lambda: len(observer.on("/state")) == 2, 5)
    assert [payload(m)["headerId"] for m in observer.on("/state")] == [2 ** 32 - 1, 0]


def test_timestamp_written_in_utc_with_z(broker, observer, agv):
    agv.start()
    assert agv.wait_connected(5)
    local = datetime(2026, 10, 6, 14, 30, 15, 123456, tzinfo=timezone(timedelta(hours=7)))
    agv.send_state(make_state(timestamp=local))
    assert wait_until(lambda: observer.on("/state"), 5)
    assert payload(observer.on("/state")[0])["timestamp"] == "2026-10-06T07:30:15.123456Z"
    for m in observer.on("/connection"):
        assert payload(m)["timestamp"].endswith("Z")


def test_naive_timestamp_is_refused(broker, observer, agv):
    agv.start()
    assert agv.wait_connected(5)
    with pytest.raises(ValidationError, match="time zone"):
        agv.send_state(make_state(timestamp=datetime(2026, 10, 6, 14, 30)))
    agv.send_state(make_state())
    assert wait_until(lambda: observer.on("/state"), 5)
    # the refused message took no headerId
    assert payload(observer.on("/state")[0])["headerId"] == 0


# ── L4: messages that are not delivered ───────────────────────────


def raw_publish(port: int, topic: str, data: bytes) -> None:
    import paho.mqtt.publish as publish
    publish.single(topic, data, hostname="127.0.0.1", port=port)


@pytest.mark.parametrize("validate", [True, False])
def test_invalid_messages_reach_the_application(broker, validate):
    agv = ThreadedAGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=broker.port,
                            validate_messages=validate)
    invalid, orders = Recorder(), Recorder()
    agv.on_invalid_message(invalid)
    agv.on_order_received(orders)
    agv.start()
    try:
        assert agv.wait_connected(5)
        raw_publish(broker.port, f"{BASE}/order", b"not json")
        raw_publish(broker.port, f"{BASE}/order", b"\xff\xfe")
        raw_publish(broker.port, f"{BASE}/instantActions", json.dumps({"headerId": 1}).encode())
        good = make_order(5)
        raw_publish(broker.port, f"{BASE}/order", good.to_mqtt_payload().encode())
        assert wait_until(lambda: len(invalid) == 3 and len(orders) >= 1, 5)
        kinds = [(m.message_type, m.kind) for m in invalid.items]
        assert kinds == [("order", "json"), ("order", "json"),
                         ("instantActions", "schema" if validate else "model")]
        for m in invalid.items:
            assert isinstance(m, InvalidMessage) and m.topic.startswith(BASE) and m.reason
        assert invalid.items[0].payload == b"not json"
        assert orders.items[0].orderId == "o5"
    finally:
        agv.stop()


def test_invalid_messages_are_logged_without_a_callback(broker, agv, caplog):
    agv.start()
    assert agv.wait_connected(5)
    raw_publish(broker.port, f"{BASE}/order", b"{")
    assert wait_until(lambda: "not delivered" in caplog.text, 5)


# ── L8: factsheet and visualization as the official schema allows ─


def test_factsheet_and_visualization_without_header_are_accepted(broker, master):
    factsheets, visualizations, invalid = Recorder(), Recorder(), Recorder()
    master.on_factsheet(factsheets)
    master.on_visualization(visualizations)
    master.on_invalid_message(invalid)
    master.start()
    assert master.wait_connected(5)
    bare_factsheet = {"version": "2.1.0", "manufacturer": MANUFACTURER, "serialNumber": SERIAL,
                      **FACTSHEET_BODY}
    raw_publish(broker.port, f"{BASE}/factsheet", json.dumps(bare_factsheet).encode())
    raw_publish(broker.port, f"{BASE}/visualization", b"{}")
    assert wait_until(lambda: len(factsheets) == 1 and len(visualizations) == 1, 5), invalid.items
    serial, fs = factsheets.items[0]
    assert serial == SERIAL and fs.headerId is None and fs.timestamp is None


def test_sent_visualization_and_factsheet_get_a_full_header(broker, observer, agv):
    from vda5050.models import Factsheet, Visualization
    agv.start()
    assert agv.wait_connected(5)
    agv.send_visualization(Visualization())
    agv.send_factsheet(Factsheet.model_validate(
        {"version": "2.1.0", "manufacturer": MANUFACTURER, "serialNumber": SERIAL,
         **FACTSHEET_BODY}))
    assert wait_until(lambda: observer.on("/visualization") and observer.on("/factsheet"), 5)
    for topic in ("/visualization", "/factsheet"):
        p = payload(observer.on(topic)[0])
        assert p["headerId"] == 0 and p["timestamp"].endswith("Z")
        header = (p["version"], p["manufacturer"], p["serialNumber"])
        assert header == ("2.1.0", MANUFACTURER, SERIAL)


# ── L7: callbacks on one thread, across reconnections ─────────────


def test_callbacks_on_one_thread_across_reconnections(broker, agv, master):
    orders = Recorder()
    agv.on_order_received(orders)
    agv.on_broker_connection(orders)
    agv.start()
    master.start()
    assert agv.wait_connected(5) and master.wait_connected(5)
    for i in range(3):
        n = len(orders)
        master.send_order(MANUFACTURER, SERIAL, make_order(i))
        assert wait_until(lambda: len(orders) > n, 5)
        broker.restart(down_for=0.2)
        assert agv.wait_connected(15) and master.wait_connected(15)
    assert len(orders.threads) == 1
    alive = [t.name for t in threading.enumerate()
             if t.name.startswith(f"paho-mqtt-client-{MANUFACTURER}_{SERIAL}")]
    assert len(alive) == 1


def test_update_connection_offline_and_online(broker, observer, agv):
    agv.start()
    assert agv.wait_connected(5)
    assert agv.update_connection(ConnectionState.OFFLINE)
    assert agv.update_connection(ConnectionState.ONLINE)
    assert wait_until(lambda: len(observer.on("/connection")) == 3, 5)
    assert [payload(m)["connectionState"] for m in observer.on("/connection")] == \
        ["ONLINE", "OFFLINE", "ONLINE"]


def test_stop_while_messages_arrive_still_sends_offline(broker, agv, master):
    orders = Recorder()
    agv.on_order_received(orders)
    agv.start()
    master.start()
    assert agv.wait_connected(5) and master.wait_connected(5)
    running = threading.Event()
    running.set()

    def flood():
        while running.is_set():
            master.send_order(MANUFACTURER, SERIAL, make_order(1))
            time.sleep(0.001)

    flooder = threading.Thread(target=flood)
    flooder.start()
    try:
        assert wait_until(lambda: len(orders) > 10, 5)
        t0 = time.monotonic()
        agv.stop()
        assert time.monotonic() - t0 < 1.5, "OFFLINE acknowledged without waiting out the timeout"
    finally:
        running.clear()
        flooder.join()
    assert payload(retained(broker.port, f"{BASE}/connection"))["connectionState"] == "OFFLINE"
