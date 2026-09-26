"""HomeSite house emulator — replaces the boiler controller and the RF gateway.

Publishes the same MQTT traffic as the real devices (sensor readings,
heartbeats, acks, scan results) driven by a physical model of a heated house
in winter, and reacts to commands/settings exactly like the firmware.

Run from the repo:
    cd tools && python -m house_emulator                       # local broker, real time
    cd tools && python -m house_emulator --speed 60            # 1 real second = 1 minute
    cd tools && python -m house_emulator --leak 1.0 --outdoor -20

Requires aiomqtt (already in the backend venv). State (house temperatures,
"NVS" settings, faults) is kept in .emulator_state.json next to this package.
"""

import argparse
import asyncio
import contextlib
import json
import random
import sys
import zlib
from datetime import datetime
from pathlib import Path

import aiomqtt

from .plant import Plant
from .settings import defaults
from .sim import CLIMATE, DS18B20, Simulation

STATE_FILE = Path(__file__).resolve().parent.parent / ".emulator_state.json"
HEARTBEAT_S = 30.0
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

# Fake OneWire addresses for scan results (stable per sensor name)
def _addr(name: str) -> str:
    return f"28{zlib.crc32(name.encode()):08X}0000"


class Emulator:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.prefix = args.prefix
        self.node = args.node
        self.rf_node = args.rf_node
        self.speed = args.speed
        plant = Plant(seed=args.seed, outdoor_base=args.outdoor, leak_bar_per_day=args.leak,
                      boiler_panel=args.boiler_panel)
        self.sim = Simulation(
            plant,
            prs_heating_name=args.prs_heating,
            prs_water_name=args.prs_water,
            local_outdoor=args.local_outdoor,
        )
        self.client: aiomqtt.Client | None = None
        self.running = True
        self.rf_uptime = 0.0
        self.rf_frames = 0
        self.rf_next: dict[str, float] = {}
        self.log: list[str] = []

    # ------------------------------------------------------------------ utils
    def say(self, msg: str) -> None:
        line = f"{datetime.now():%H:%M:%S}  {msg}"
        self.log.append(line)
        del self.log[:-200]
        if not self.args.quiet:
            print(line, flush=True)

    async def publish(self, topic: str, payload: dict | list, qos: int = 0) -> None:
        if self.client is None:
            return
        with contextlib.suppress(aiomqtt.MqttError):
            await self.client.publish(self.prefix + topic, json.dumps(payload), qos=qos)

    # ------------------------------------------------------------------ periodic tasks
    async def physics_loop(self) -> None:
        tick = 1.0
        while self.running:
            await asyncio.sleep(tick)
            self.sim.advance(tick * self.speed)
            self.rf_uptime += tick * self.speed
            for line in self.sim.controller.log:
                self.say(f"[{self.node}] {line}")
            self.sim.controller.log.clear()

    async def boiler_publish_loop(self) -> None:
        """Firmware: every read interval publish each DS18B20 + pressure sensors.

        Cadence is in real seconds regardless of --speed, so the gateway and the
        database see the same message rate as from the real controller.
        """
        while self.running:
            await asyncio.sleep(self.sim.read_interval)
            for name, value in self.sim.boiler_readings().items():
                await self.publish(name, {"tmp": value})
            if self.args.prs_heating and (p := self.sim.heating_pressure_reading()) is not None:
                await self.publish(self.args.prs_heating, {"prs": p})
            if self.args.prs_water and (p := self.sim.water_pressure_reading()) is not None:
                await self.publish(self.args.prs_water, {"prs": p})

    async def publish_heartbeats(self) -> None:
        hb = self.sim.controller.heartbeat(
            self.sim.heating_pressure_reading() if self.args.prs_heating else None,
            self.sim.water_pressure_reading() if self.args.prs_water else None,
        )
        await self.publish(f"{self.node}/heartbeat", hb)
        await self.publish(f"{self.rf_node}/heartbeat", {
            "uptime": int(self.rf_uptime), "free_heap": 151_000, "frames_ok": self.rf_frames,
            "frames_unknown": self.rf_frames // 40, "seen": len(CLIMATE), "raw_debug": False,
        })

    async def heartbeat_loop(self) -> None:
        while self.running:
            await self.publish_heartbeats()
            await asyncio.sleep(HEARTBEAT_S)

    async def rf_loop(self) -> None:
        """BL999 sensors transmit every 30–60 s; ~3 % of packets are lost."""
        loop = asyncio.get_running_loop()
        rng = random.Random(self.args.seed + 99)
        for name in CLIMATE:
            self.rf_next[name] = loop.time() + rng.uniform(1, 30)
        while self.running:
            await asyncio.sleep(1)
            now = loop.time()
            for name in CLIMATE:
                if now < self.rf_next[name]:
                    continue
                self.rf_next[name] = now + rng.uniform(30, 60)
                if rng.random() < 0.03:
                    continue
                reading = self.sim.climate_reading(name)
                if reading is not None:
                    self.rf_frames += 1
                    await self.publish(name, reading)

    async def autosave_loop(self) -> None:
        while self.running:
            await asyncio.sleep(60)
            self.save()

    def save(self) -> None:
        with contextlib.suppress(OSError):
            self.sim.save(STATE_FILE)

    # ------------------------------------------------------------------ commands
    async def on_boiler_command(self, data: dict) -> None:
        c = self.sim.controller
        ack: dict[str, str] = {}
        restart = False
        for key, raw in data.items():
            value = str(raw)
            self.say(f"[{self.node}] ◄ {key} = {value}")
            if key == "restart":
                ack[key], restart = "ok", True
            elif key == "reset_config":
                c.settings = defaults()
                c.autofill_fault = False
                ack[key], restart = "ok", True
            elif key == "autofill_reset":
                c.reset_autofill_fault()
                ack[key] = "ok"
            elif key == "outdoor_temp":
                with contextlib.suppress(ValueError):
                    if not self.sim.local_outdoor:
                        c.set_outdoor(float(value))
            elif key == "interval":
                try:
                    seconds = int(value)
                except ValueError:
                    seconds = 0
                if 5 <= seconds <= 600:
                    self.sim.read_interval = float(seconds)
                    ack[key] = "ok"
                else:
                    ack[key] = "invalid_value"
            elif key in ("node_name", "timezone", "mqtt_host", "mqtt_port", "mqtt_user", "mqtt_pass"):
                ack[key] = "ok"  # accepted; the emulator keeps its CLI settings
            elif key == "scan_sensors":
                await self.publish(f"{self.node}/sensors", [
                    {"addr": _addr(n), "type": "ds18b20", "temp": round(self.sim.plant.pipes[n], 1), "name": n}
                    for n in DS18B20 if n not in self.sim.failed
                ], qos=1)
            elif key in ("sensor_assign", "sensor_remove"):
                pass  # no generic ack, like the firmware
            elif key == "sensor_offset":
                parts = value.split(":")
                if len(parts) == 3:
                    with contextlib.suppress(ValueError):
                        self.sim.offsets[f"{parts[0]}:{parts[1]}"] = float(parts[2])
            else:
                ack[key] = c.on_setting(key, value)
                if ack[key] != "ok":
                    self.say(f"[{self.node}]   rejected: {ack[key]}")
        if ack:
            await self.publish(f"{self.node}/ack", ack, qos=1)
        # Like the firmware: report the new relay state right away, not in ≤30 s —
        # but not for the outdoor_temp telemetry the gateway forwards on every street reading
        if not restart and set(data) != {"outdoor_temp"}:
            self.sim.controller.update(
                self.sim.now, self.sim.boiler_readings(), self.sim.heating_pressure_reading() or 0.0
            )
            await self.publish_heartbeats()
        if restart:
            await asyncio.sleep(0.5)
            c.reboot()
            self.say(f"[{self.node}] ↻ rebooted (relays off, settings from NVS)")
            self.save()

    async def on_rf_command(self, data: dict) -> None:
        ack = {}
        for key, raw in data.items():
            self.say(f"[{self.rf_node}] ◄ {key} = {raw}")
            if key == "restart":
                self.rf_uptime = 0
                ack[key] = "ok"
            elif key == "scan_sensors":
                await self.publish(f"{self.rf_node}/sensors", [
                    {"model": "BL999", "id": 100 + i, "channel": i % 3 + 1, "name": n}
                    for i, n in enumerate(CLIMATE)
                ], qos=1)
            elif key not in ("sensor_assign", "sensor_remove", "sensor_offset"):
                ack[key] = "ok"
        if ack:
            await self.publish(f"{self.rf_node}/ack", ack, qos=1)

    async def mqtt_loop(self) -> None:
        kwargs = {"hostname": self.args.host, "port": self.args.port, "identifier": f"house-emulator-{self.node}"}
        if self.args.user:
            kwargs.update(username=self.args.user, password=self.args.password)
        while self.running:
            try:
                async with aiomqtt.Client(**kwargs) as client:
                    self.client = client
                    # Fresh "boot" from the gateway's point of view → it re-sends config_kv
                    self.say(f"MQTT connected {self.args.host}:{self.args.port}")
                    await client.subscribe(f"{self.prefix}{self.node}/cmd", qos=1)
                    await client.subscribe(f"{self.prefix}{self.rf_node}/cmd", qos=1)
                    async for message in client.messages:
                        try:
                            data = json.loads(message.payload)
                        except (ValueError, TypeError):
                            continue
                        if not isinstance(data, dict):
                            continue
                        if str(message.topic).startswith(f"{self.prefix}{self.node}/"):
                            await self.on_boiler_command(data)
                        else:
                            await self.on_rf_command(data)
            except aiomqtt.MqttError as e:
                self.client = None
                self.say(f"MQTT error: {e} — reconnecting in 5 s")
                await asyncio.sleep(5)

    # ------------------------------------------------------------------ console
    HELP = """Commands:
  status                  current state of the house and the boiler room
  leak <bar/day>          heating circuit leak rate (0 = tight)
  pressure <bar>          set circuit pressure now (e.g. after bleeding air)
  outdoor <°C>            winter base temperature (cold snap / thaw)
  dhw <min> [l/min]       open a hot water tap now
  fail <sensor>|list      stop a sensor from reporting (e.g. fail tsboiler_s)
  fix <sensor>|all        bring sensors back
  speed <x>               simulation speed (1 = real time)
  log                     last events
  quit"""

    async def console_loop(self) -> None:
        loop = asyncio.get_running_loop()
        print(self.HELP, flush=True)
        while self.running:
            line = await loop.run_in_executor(None, sys.stdin.readline)
            if not line:
                await asyncio.sleep(3600)  # stdin closed (service mode)
                continue
            parts = line.split()
            if not parts:
                continue
            try:
                self.console(parts)
            except (ValueError, IndexError):
                print("  bad arguments — see 'help'")

    def console(self, parts: list[str]) -> None:
        cmd, args = parts[0].lower(), parts[1:]
        sim, plant = self.sim, self.sim.plant
        if cmd == "status":
            for k, v in sim.status().items():
                print(f"  {k:<14} {v}")
        elif cmd == "leak":
            plant.leak_bar_per_day = max(0.0, float(args[0]))
            print(f"  leak = {plant.leak_bar_per_day} bar/day")
        elif cmd == "pressure":
            plant.charge += float(args[0]) - plant.heating_pressure()
            print(f"  pressure = {plant.heating_pressure():.2f} bar")
        elif cmd == "outdoor":
            plant.outdoor_base = float(args[0])
            print(f"  outdoor base = {plant.outdoor_base} °C")
        elif cmd == "dhw":
            sim.start_draw(float(args[0]), float(args[1]) if len(args) > 1 else 7.0)
            print("  tap opened")
        elif cmd == "fail":
            if args[0] == "list":
                print("  " + ", ".join(DS18B20 + CLIMATE + [self.args.prs_heating, self.args.prs_water]))
            else:
                sim.failed.add(args[0])
                print(f"  {args[0]} silent")
        elif cmd == "fix":
            sim.failed = set() if args[0] == "all" else sim.failed - {args[0]}
            print(f"  failed: {sorted(sim.failed) or '—'}")
        elif cmd == "speed":
            self.speed = max(0.1, float(args[0]))
            print(f"  speed ×{self.speed}")
        elif cmd == "log":
            print("\n".join(self.log[-30:]))
        elif cmd in ("quit", "exit", "q"):
            self.running = False
        else:
            print(self.HELP)

    # ------------------------------------------------------------------ main
    async def run(self) -> None:
        if not self.args.fresh and self.sim.load(STATE_FILE):
            self.say(f"state restored from {STATE_FILE.name}")
        else:
            self.say("warm start: simulating 3 h so the house and the boiler room settle")
            self.sim.warmup(3)
        tasks = [
            self.physics_loop(), self.boiler_publish_loop(), self.heartbeat_loop(),
            self.rf_loop(), self.autosave_loop(), self.mqtt_loop(),
        ]
        if not self.args.no_console:
            tasks.append(self.console_loop())
        runners = [asyncio.create_task(t) for t in tasks]
        try:
            while self.running:
                await asyncio.sleep(0.5)
        finally:
            for r in runners:
                r.cancel()
            self.save()
            self.say("state saved, bye")


def main() -> None:
    p = argparse.ArgumentParser(description="HomeSite house emulator (boiler_unit + rf-gateway)")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--user", default="")
    p.add_argument("--password", default="")
    p.add_argument("--prefix", default="home/devices/")
    p.add_argument("--node", default="boiler_unit")
    p.add_argument("--rf-node", default="rf-gateway")
    p.add_argument("--prs-heating", default="prs_heating", help="heating pressure sensor name ('' = none)")
    p.add_argument("--prs-water", default="prs_water", help="mains pressure sensor name ('' = none)")
    p.add_argument("--speed", type=float, default=1.0, help="simulated seconds per real second")
    p.add_argument("--outdoor", type=float, default=-12.0, help="winter base outdoor temperature, °C")
    p.add_argument("--leak", type=float, default=0.3, help="heating circuit leak, bar/day")
    p.add_argument("--boiler-panel", type=float, default=75.0, help="boiler's own thermostat, °C")
    p.add_argument("--local-outdoor", action="store_true",
                   help="feed the street sensor to the controller directly (no gateway forwarding)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--fresh", action="store_true", help="ignore saved state")
    p.add_argument("--no-console", action="store_true", help="no interactive console (service mode)")
    p.add_argument("--quiet", action="store_true", help="don't echo events")
    p.add_argument("--allow-remote", action="store_true",
                   help="allow a non-local broker (the emulator writes fake data into that system's DB)")
    args = p.parse_args()

    if args.host not in LOCAL_HOSTS and not args.allow_remote:
        p.error(f"{args.host} is not local. Emulated readings would land in that system's database; "
                "pass --allow-remote if that is intended.")

    try:
        asyncio.run(Emulator(args).run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
