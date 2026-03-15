#!/usr/bin/env python3
"""ESP32 Device Emulator — simulates a real ESP32 node for testing.

Connects to MQTT broker, publishes sensor data, receives commands,
sends acks and heartbeats. Shows all activity in real-time.

Usage:
    python -m tools.esp32_emulator [--node boiler_unit] [--host 127.0.0.1] [--port 1883]
"""

import argparse
import asyncio
import json
import random
import sys
from datetime import UTC, datetime

import aiomqtt

# ANSI colors
C_RESET = "\033[0m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_RED = "\033[91m"
C_DIM = "\033[90m"
C_BOLD = "\033[1m"


def ts() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def log_send(topic: str, payload: str) -> None:
    print(f"  {C_DIM}{ts()}{C_RESET}  {C_GREEN}>>> SEND{C_RESET}  {topic}")
    print(f"           {C_DIM}{payload}{C_RESET}")


def log_recv(topic: str, payload: str) -> None:
    print(f"  {C_DIM}{ts()}{C_RESET}  {C_YELLOW}<<< RECV{C_RESET}  {topic}")
    print(f"           {C_BOLD}{payload}{C_RESET}")


def log_info(msg: str) -> None:
    print(f"  {C_DIM}{ts()}{C_RESET}  {C_CYAN}--- INFO{C_RESET}  {msg}")


def log_error(msg: str) -> None:
    print(f"  {C_DIM}{ts()}{C_RESET}  {C_RED}!!! ERR {C_RESET}  {msg}")


class SensorSimulator:
    """Simulates sensor readings with realistic drift."""

    def __init__(self) -> None:
        self.sensors: dict[str, dict] = {
            "tsboiler_s_t": {"type": "tmp", "base": 65, "drift": 5},
            "tsboiler_b_t": {"type": "tmp", "base": 50, "drift": 5},
            "tsrad_s_t": {"type": "tmp", "base": 45, "drift": 3},
            "tsrad_b_t": {"type": "tmp", "base": 35, "drift": 3},
            "tsfloor_s_t": {"type": "tmp", "base": 30, "drift": 2},
            "tsfloor_b_t": {"type": "tmp", "base": 25, "drift": 2},
            "tsihb_s_t": {"type": "tmp", "base": 55, "drift": 4},
            "tsihb_b_t": {"type": "tmp", "base": 45, "drift": 4},
            "tsboiler_s_p": {"type": "prs", "base": 1.5, "drift": 0.1},
            "tsfloor_s_p": {"type": "prs", "base": 1.0, "drift": 0.1},
            "tsihb_s_p": {"type": "prs", "base": 2.0, "drift": 0.2},
            "clm_street_thp": {"type": "multi", "values": {
                "tmp": {"base": 5, "drift": 3},
                "hmt": {"base": 70, "drift": 10},
                "prs": {"base": 1013, "drift": 5},
            }},
            "clm_chl_th": {"type": "multi", "values": {
                "tmp": {"base": 22, "drift": 1},
                "hmt": {"base": 45, "drift": 5},
            }},
        }

    def read(self, name: str) -> dict[str, float]:
        """Generate a reading for a sensor."""
        cfg = self.sensors[name]
        if cfg["type"] == "multi":
            return {
                k: round(v["base"] + random.uniform(-v["drift"], v["drift"]), 1)
                for k, v in cfg["values"].items()
            }
        return {
            cfg["type"]: round(cfg["base"] + random.uniform(-cfg["drift"], cfg["drift"]), 2)
        }


class ESP32Emulator:
    def __init__(self, node_name: str, host: str, port: int, prefix: str, interval: int) -> None:
        self.node_name = node_name
        self.host = host
        self.port = port
        self.prefix = prefix
        self.interval = interval
        self.simulator = SensorSimulator()
        self._settings: dict[str, str] = {}

    async def run(self) -> None:
        print()
        print(f"  {C_BOLD}═══════════════════════════════════════════════════{C_RESET}")
        print(f"  {C_BOLD}  ESP32 Emulator: {C_CYAN}{self.node_name}{C_RESET}")
        print(f"  {C_BOLD}  MQTT: {self.host}:{self.port}{C_RESET}")
        print(f"  {C_BOLD}  Prefix: {self.prefix}{C_RESET}")
        print(f"  {C_BOLD}  Sensor interval: {self.interval}s{C_RESET}")
        print(f"  {C_BOLD}═══════════════════════════════════════════════════{C_RESET}")
        print()

        while True:
            try:
                await self._connect_and_run()
            except aiomqtt.MqttError as e:
                log_error(f"MQTT disconnected: {e}")
                log_info("Reconnecting in 5s...")
                await asyncio.sleep(5)
            except Exception as e:
                log_error(f"Unexpected: {e}")
                await asyncio.sleep(5)

    async def _connect_and_run(self) -> None:
        async with aiomqtt.Client(hostname=self.host, port=self.port) as client:
            log_info(f"Connected to MQTT {self.host}:{self.port}")

            # Subscribe to commands
            cmd_topic = f"{self.prefix}{self.node_name}/cmd"
            await client.subscribe(cmd_topic)
            log_info(f"Subscribed to {cmd_topic}")

            # Run tasks concurrently
            await asyncio.gather(
                self._publish_sensors(client),
                self._publish_heartbeat(client),
                self._listen_commands(client),
            )

    async def _publish_sensors(self, client: aiomqtt.Client) -> None:
        """Publish sensor readings at configured interval."""
        while True:
            for name, cfg in self.simulator.sensors.items():
                reading = self.simulator.read(name)
                topic = f"{self.prefix}{name}"
                payload = json.dumps(reading)
                await client.publish(topic, payload)
                log_send(topic, payload)

            await asyncio.sleep(self.interval)

    async def _publish_heartbeat(self, client: aiomqtt.Client) -> None:
        """Publish heartbeat every 30 seconds."""
        while True:
            topic = f"{self.prefix}{self.node_name}/heartbeat"
            payload = json.dumps({"uptime": random.randint(1000, 999999)})
            await client.publish(topic, payload)
            log_send(topic, payload)
            await asyncio.sleep(30)

    async def _listen_commands(self, client: aiomqtt.Client) -> None:
        """Listen for commands and send ack."""
        async for message in client.messages:
            topic = str(message.topic)
            raw = message.payload
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode()

            log_recv(topic, raw)

            # Parse and apply settings
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    ack_payload: dict[str, str] = {}
                    for key, value in data.items():
                        old = self._settings.get(key, "?")
                        self._settings[key] = str(value)
                        log_info(f"Applied: {key} = {value} (was {old})")
                        ack_payload[key] = "ok"

                    # Send ack
                    ack_topic = f"{self.prefix}{self.node_name}/ack"
                    ack_json = json.dumps(ack_payload)
                    await client.publish(ack_topic, ack_json)
                    log_send(ack_topic, ack_json)
            except json.JSONDecodeError:
                log_error(f"Invalid JSON: {raw}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ESP32 Device Emulator")
    parser.add_argument("--node", default="boiler_unit", help="Node name (default: boiler_unit)")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--prefix", default="home/devices/", help="MQTT topic prefix")
    parser.add_argument("--interval", type=int, default=5, help="Sensor publish interval in seconds")
    args = parser.parse_args()

    emulator = ESP32Emulator(
        node_name=args.node,
        host=args.host,
        port=args.port,
        prefix=args.prefix,
        interval=args.interval,
    )

    try:
        asyncio.run(emulator.run())
    except KeyboardInterrupt:
        print(f"\n  {C_DIM}Emulator stopped.{C_RESET}")


if __name__ == "__main__":
    main()
