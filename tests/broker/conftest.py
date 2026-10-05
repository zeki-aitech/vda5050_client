"""
Fixtures for the tests that run against a real MQTT broker (see
mqtt_broker.py). Without a mosquitto binary these tests are skipped, unless
VDA5050_REQUIRE_BROKER=1 (CI sets it), in which case they fail.
"""

import os

import pytest

from .mqtt_broker import MOSQUITTO, Broker, Observer


@pytest.fixture
def broker(tmp_path):
    if MOSQUITTO is None:
        if os.environ.get("VDA5050_REQUIRE_BROKER") == "1":
            pytest.fail("mosquitto not found and VDA5050_REQUIRE_BROKER=1")
        pytest.skip("mosquitto not installed")
    b = Broker(tmp_path)
    b.start()
    yield b
    b.stop()


@pytest.fixture
def observer(broker):
    o = Observer(broker.port)
    yield o
    o.close()
