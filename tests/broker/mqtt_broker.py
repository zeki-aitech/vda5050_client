"""
Helpers for the tests that run against a real MQTT broker.

Each test gets its own mosquitto, started on 127.0.0.1 on a free port, so the
tests never touch a broker already running on the machine (1883). The broker
can be stopped and started again on the same port to test reconnection.

Without a mosquitto binary these tests are skipped, unless the environment
sets VDA5050_REQUIRE_BROKER=1 (CI does), in which case they fail.
"""

import os
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import List, Optional

import paho.mqtt.client as mqtt

MOSQUITTO = shutil.which("mosquitto") or (
    "/usr/sbin/mosquitto" if os.path.exists("/usr/sbin/mosquitto") else None
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_until(predicate, timeout: float, interval: float = 0.05) -> bool:
    """Poll predicate until it is true or the timeout expires."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class Broker:
    """A private mosquitto on 127.0.0.1 that a test can stop and start."""

    def __init__(self, workdir: Path):
        self.port = _free_port()
        self.conf = workdir / "mosquitto.conf"
        self.conf.write_text(
            f"listener {self.port} 127.0.0.1\n"
            "allow_anonymous true\n"
            "persistence false\n"
        )
        self.log = workdir / "mosquitto.log"
        self._proc: Optional[subprocess.Popen] = None

    def start(self) -> None:
        assert self._proc is None, "broker already running"
        with open(self.log, "a") as log:
            self._proc = subprocess.Popen(
                [MOSQUITTO, "-c", str(self.conf), "-v"], stdout=log, stderr=log
            )
        if not wait_until(self._listening, timeout=10):
            raise RuntimeError(f"mosquitto did not start on port {self.port}")

    def stop(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            self._proc.wait(timeout=10)
            self._proc = None

    def restart(self, down_for: float = 1.0) -> None:
        self.stop()
        time.sleep(down_for)
        self.start()

    def _listening(self) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                return True
        except OSError:
            return False


class Observer:
    """
    A plain paho client that subscribes to everything with QoS 1, so each
    message it receives shows the QoS and retain flag it was published with.
    """

    def __init__(self, port: int):
        self.messages: List[mqtt.MQTTMessage] = []
        self._lock = threading.Lock()
        self._subscribed = threading.Event()
        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self._client.on_message = self._on_message
        self._client.on_subscribe = lambda *a: self._subscribed.set()
        self._client.connect("127.0.0.1", port)
        self._client.subscribe("#", qos=1)
        self._client.loop_start()
        assert self._subscribed.wait(5), "observer could not subscribe"

    def _on_message(self, client, userdata, msg):
        with self._lock:
            self.messages.append(msg)

    def on(self, topic_suffix: str) -> List[mqtt.MQTTMessage]:
        with self._lock:
            return [m for m in self.messages if m.topic.endswith(topic_suffix)]

    def clear(self) -> None:
        with self._lock:
            self.messages.clear()

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()


def retained(port: int, topic: str, timeout: float = 2.0) -> Optional[mqtt.MQTTMessage]:
    """The retained message the broker holds on a topic, or None."""
    got: List[mqtt.MQTTMessage] = []
    done = threading.Event()

    def on_message(client, userdata, msg):
        if msg.retain:
            got.append(msg)
            done.set()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    c.on_message = on_message
    c.connect("127.0.0.1", port)
    c.subscribe(topic, qos=1)
    c.loop_start()
    done.wait(timeout)
    c.disconnect()
    c.loop_stop()
    return got[0] if got else None
