"""
The threaded clients and the transport without a broker: the header,
outgoing checks, the receive path and the connection states. What needs a
broker is in tests/broker/.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import paho.mqtt.client as mqtt
import pytest
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from vda5050 import AGVClient, ThreadedAGVClient, ThreadedMasterControlClient
from vda5050.core.mqtt_abstraction import ConnectionState as MQTTState
from vda5050.core.threaded_client import RETAINED_TOPICS, TOPIC_QOS
from vda5050.core.transport import MQTTTransport
from vda5050.models import Visualization
from vda5050.utils.exceptions import ValidationError

from ..broker.messages import MANUFACTURER, SERIAL, make_order, make_state

TOPIC = f"uagv/v2/{MANUFACTURER}/{SERIAL}"


def message(topic: str, payload: bytes) -> mqtt.MQTTMessage:
    m = mqtt.MQTTMessage(topic=topic.encode())
    m.payload = payload
    return m


@pytest.fixture
def agv():
    return ThreadedAGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=1)


def test_qos_and_retain_are_those_of_the_standard():
    assert TOPIC_QOS == {"order": 0, "instantActions": 0, "state": 0, "visualization": 0,
                         "factsheet": 0, "connection": 1}
    assert RETAINED_TOPICS == {"connection", "factsheet"}


def test_publish_when_not_connected_returns_false(agv):
    assert agv.send_state(make_state()) is False
    assert agv._next_header_id == {}


def test_payload_sets_header_id_and_utc_timestamp(agv):
    agv._next_header_id[f"{TOPIC}/state"] = 41
    local = datetime(2026, 1, 2, 3, 4, 5, 678901, tzinfo=timezone(timedelta(hours=-5)))
    state = make_state(n=7, timestamp=local)
    p = json.loads(agv._payload("state", state, f"{TOPIC}/state"))
    assert p["headerId"] == 41
    assert p["timestamp"] == "2026-01-02T08:04:05.678901Z"
    assert state.headerId == 7 and state.timestamp == local, "the caller's message is not changed"


def test_payload_refuses_a_naive_timestamp(agv):
    with pytest.raises(ValidationError, match="time zone"):
        agv._payload("state", make_state(timestamp=datetime(2026, 1, 2)), f"{TOPIC}/state")


def test_payload_fills_an_empty_header(agv):
    p = json.loads(agv._payload("visualization", Visualization(), f"{TOPIC}/visualization"))
    assert set(p) == {"headerId", "timestamp", "version", "manufacturer", "serialNumber"}
    assert p["timestamp"].endswith("Z")


def test_payload_checked_against_the_schema(agv):
    bad = make_state().model_copy(update={"driving": None})  # dropped on serialisation
    with pytest.raises(ValidationError, match="driving"):
        agv._payload("state", bad, f"{TOPIC}/state")


def test_without_validation_the_schema_is_not_checked():
    c = ThreadedAGVClient("127.0.0.1", MANUFACTURER, SERIAL, validate_messages=False)
    bad = make_state().model_copy(update={"driving": None})  # dropped on serialisation
    assert "driving" not in c._payload("state", bad, f"{TOPIC}/state")


def test_last_will_is_connectionbroken_retained_qos1(agv):
    agv.transport.set_will = MagicMock()
    agv._before_start()
    (topic, payload), kwargs = agv.transport.set_will.call_args
    assert topic == f"{TOPIC}/connection"
    assert json.loads(payload)["connectionState"] == "CONNECTIONBROKEN"
    assert json.loads(payload)["headerId"] == 0
    assert kwargs == {"qos": 1, "retain": True}
    assert agv._next_header_id[f"{TOPIC}/connection"] == 1


def test_receive_delivers_a_valid_order(agv):
    got = []
    agv.on_order_received(got.append)
    agv._receive("order", f"{TOPIC}/order",
                 message(f"{TOPIC}/order", make_order(3).to_mqtt_payload().encode()))
    assert [o.orderId for o in got] == ["o3"]


@pytest.mark.parametrize("payload,kind", [
    (b"", "json"),
    (b"\xff", "json"),
    (b"[1,", "json"),
    (b"{}", "schema"),
])
def test_receive_reports_what_it_does_not_deliver(agv, payload, kind):
    got, invalid = [], []
    agv.on_order_received(got.append)
    agv.on_invalid_message(invalid.append)
    agv._receive("order", f"{TOPIC}/order", message(f"{TOPIC}/order", payload))
    assert got == []
    assert [(m.topic, m.message_type, m.kind, m.payload) for m in invalid] == \
        [(f"{TOPIC}/order", "order", kind, payload)]
    assert invalid[0].reason


def test_receive_reports_a_model_failure_when_not_validating():
    c = ThreadedAGVClient("127.0.0.1", MANUFACTURER, SERIAL, validate_messages=False)
    invalid = []
    c.on_invalid_message(invalid.append)
    c._receive("order", f"{TOPIC}/order", message(f"{TOPIC}/order", b"{}"))
    assert [m.kind for m in invalid] == ["model"]


def test_callback_exception_does_not_escape(agv):
    agv.on_order_received(lambda o: 1 / 0)
    agv._receive("order", f"{TOPIC}/order",
                 message(f"{TOPIC}/order", make_order(3).to_mqtt_payload().encode()))


def test_master_passes_the_serial_number_from_the_topic():
    mc = ThreadedMasterControlClient("127.0.0.1", "M", "master")
    got = []
    mc.on_state_update(lambda serial, st: got.append(serial))
    mc._receive("state", "uagv/v2/+/+/state",
                message("uagv/v2/Other/robot-7/state", make_state().to_mqtt_payload().encode()))
    assert got == ["robot-7"]


# ── transport states ──────────────────────────────────────────────


def rc(name: str) -> ReasonCode:
    return ReasonCode(PacketTypes.CONNACK, name)


def test_transport_states_and_listeners():
    t = MQTTTransport("127.0.0.1", 1)
    t.paho = MagicMock()
    seen = []
    t.add_listener(seen.append)
    t.subscribe("a/+/b", 0, lambda m: None)
    assert t._state is MQTTState.DISCONNECTED
    t._started = True
    t._state = MQTTState.CONNECTING
    t._on_connect_fail(None, None)
    assert t._state is MQTTState.CONNECTING and t._attempted.is_set() and not t.is_connected()
    t._on_connect(None, None, None, rc("Success"))
    assert t.is_connected() and seen == [True]
    t.paho.subscribe.assert_called_with([("a/+/b", 0)])
    t._on_disconnect(None, None, None, rc("Unspecified error"))
    assert t._state is MQTTState.RECONNECTING and not t.is_connected() and seen == [True, False]
    t._on_connect(None, None, None, rc("Not authorized"))
    assert t._state is MQTTState.RECONNECTING and seen == [True, False]


def test_transport_publish_refused_when_not_connected():
    t = MQTTTransport("127.0.0.1", 1)
    t.paho = MagicMock()
    assert t.publish("x", "{}") is False
    t.paho.publish.assert_not_called()


def test_asyncio_send_state_returns_false_when_not_connected():
    agv = AGVClient("127.0.0.1", MANUFACTURER, SERIAL, broker_port=1)
    assert asyncio.run(agv.send_state(make_state())) is False
    assert agv.is_connected() is False
    assert agv.mqtt._state is MQTTState.DISCONNECTED
