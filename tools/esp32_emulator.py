#!/usr/bin/env python3
"""
ESP32 Sensor Emulator — interactive MQTT-based sensor simulator.

Emulates ESP32 devices sending sensor data to the HomeSite DeviceGateway
via MQTT. Supports adding/removing/pausing virtual sensors with realistic
temperature, humidity, and pressure readings.

Usage:
    python tools/esp32_emulator.py [--host 127.0.0.1] [--port 1883]
"""

import argparse
import json
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt

MQTT_TOPIC_PREFIX = "home/devices/"
STATE_FILE = Path(__file__).parent / ".esp32_emulator_state.json"

# Sensor type presets
SENSOR_PRESETS = {
    "temp": {
        "description": "DS18B20 (температура)",
        "params": {"tmp": (15.0, 80.0)},
    },
    "climate": {
        "description": "DHT22 (температура + влажность)",
        "params": {"tmp": (18.0, 30.0), "hmt": (30.0, 80.0)},
    },
    "full": {
        "description": "BME280 (температура + влажность + атм. давление)",
        "params": {"tmp": (18.0, 30.0), "hmt": (30.0, 80.0), "prs": (990.0, 1030.0)},
    },
    "pressure": {
        "description": "Датчик давления (давление в системе, бар)",
        "params": {"prs": (0.8, 2.5)},
    },
}


@dataclass
class VirtualSensor:
    name: str
    preset: str
    interval: float = 10.0
    paused: bool = False
    values: dict = field(default_factory=dict)
    msg_count: int = 0

    def __post_init__(self):
        params = SENSOR_PRESETS[self.preset]["params"]
        for key, (lo, hi) in params.items():
            self.values[key] = round(random.uniform(lo, hi), 1)

    def generate(self) -> dict:
        """Generate next reading with realistic drift."""
        params = SENSOR_PRESETS[self.preset]["params"]
        payload = {}
        for key, (lo, hi) in params.items():
            # Smaller drift for pressure sensors (bar range is narrow)
            if self.preset == "pressure":
                drift = random.uniform(-0.02, 0.02)
                decimals = 2
            else:
                drift = random.uniform(-0.5, 0.5)
                decimals = 1
            self.values[key] = round(
                max(lo, min(hi, self.values[key] + drift)), decimals
            )
            payload[key] = self.values[key]
        self.msg_count += 1
        return payload


class ESP32Emulator:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.sensors: dict[str, VirtualSensor] = {}
        self.client = mqtt.Client(client_id=f"esp32-emulator-{random.randint(1000,9999)}")
        self.running = True
        self._lock = threading.Lock()

    def _save_state(self):
        """Persist sensor list to disk."""
        state = [
            {"name": s.name, "preset": s.preset, "paused": s.paused, "values": s.values}
            for s in self.sensors.values()
        ]
        try:
            STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2))
        except Exception:
            pass

    def _load_state(self):
        """Restore sensors from previous session."""
        if not STATE_FILE.exists():
            return
        try:
            state = json.loads(STATE_FILE.read_text())
            for entry in state:
                if entry["preset"] not in SENSOR_PRESETS:
                    continue
                s = VirtualSensor(name=entry["name"], preset=entry["preset"], paused=entry.get("paused", False))
                s.values = entry.get("values", s.values)
                self.sensors[s.name] = s
            if self.sensors:
                print(f"  ↻ Восстановлено {len(self.sensors)} датчик(ов) из предыдущей сессии")
        except Exception:
            pass

    def connect(self):
        try:
            self.client.connect(self.host, self.port)
            self.client.loop_start()
            print(f"\n  ✓ Подключено к MQTT брокеру {self.host}:{self.port}\n")
        except Exception as e:
            print(f"\n  ✗ Ошибка подключения: {e}")
            sys.exit(1)

    def _publish_loop(self):
        """Background thread: publish sensor data at intervals."""
        while self.running:
            with self._lock:
                for sensor in self.sensors.values():
                    if sensor.paused:
                        continue
                    payload = sensor.generate()
                    topic = f"{MQTT_TOPIC_PREFIX}{sensor.name}"
                    self.client.publish(topic, json.dumps(payload), qos=1)
            time.sleep(1)

    def add_sensor(self, name: str, preset: str, interval: float = 10.0):
        with self._lock:
            if name in self.sensors:
                print(f"  ✗ Датчик '{name}' уже существует")
                return
            self.sensors[name] = VirtualSensor(name=name, preset=preset, interval=interval)
            print(f"  ✓ Добавлен: {name} ({SENSOR_PRESETS[preset]['description']})")
            self._save_state()

    def remove_sensor(self, name: str):
        with self._lock:
            if name in self.sensors:
                del self.sensors[name]
                print(f"  ✓ Удалён: {name}")
                self._save_state()
            else:
                print(f"  ✗ Датчик '{name}' не найден")

    def pause_sensor(self, name: str):
        with self._lock:
            if name not in self.sensors:
                print(f"  ✗ Датчик '{name}' не найден")
                return
            s = self.sensors[name]
            s.paused = not s.paused
            status = "приостановлен" if s.paused else "возобновлён"
            print(f"  ✓ {name}: {status}")
            self._save_state()

    def list_sensors(self):
        with self._lock:
            if not self.sensors:
                print("  (нет датчиков)")
                return
            print()
            print(f"  {'Имя':<25} {'Тип':<12} {'Статус':<14} {'Сообщ.':<8} {'Последние значения'}")
            print(f"  {'─'*25} {'─'*12} {'─'*14} {'─'*8} {'─'*30}")
            for s in self.sensors.values():
                status = "⏸  пауза" if s.paused else "▶  активен"
                vals = ", ".join(f"{k}={v}" for k, v in s.values.items())
                print(f"  {s.name:<25} {s.preset:<12} {status:<14} {s.msg_count:<8} {vals}")
            print()

    def send_once(self, name: str):
        """Send a single reading immediately."""
        with self._lock:
            if name not in self.sensors:
                print(f"  ✗ Датчик '{name}' не найден")
                return
            s = self.sensors[name]
            payload = s.generate()
            topic = f"{MQTT_TOPIC_PREFIX}{s.name}"
            self.client.publish(topic, json.dumps(payload), qos=1)
            print(f"  → {topic}: {json.dumps(payload)}")

    def run(self):
        self._load_state()
        self.connect()

        # Start publish thread
        pub_thread = threading.Thread(target=self._publish_loop, daemon=True)
        pub_thread.start()

        self._print_help()

        while self.running:
            try:
                cmd = input("\nesp32> ").strip()
                if not cmd:
                    continue
                self._handle_command(cmd)
            except (KeyboardInterrupt, EOFError):
                print("\n\n  Выход...")
                self.running = False

        self.client.loop_stop()
        self.client.disconnect()

    def _print_help(self):
        print("  ╔══════════════════════════════════════════════════════════╗")
        print("  ║          ESP32 Sensor Emulator — HomeSite v2           ║")
        print("  ╠══════════════════════════════════════════════════════════╣")
        print("  ║  add <имя> <тип>     — добавить датчик                 ║")
        print("  ║     типы: temp, climate, full                          ║")
        print("  ║  rm <имя>            — удалить датчик                  ║")
        print("  ║  pause <имя>         — приостановить/возобновить       ║")
        print("  ║  send <имя>          — отправить одно показание        ║")
        print("  ║  list                — список датчиков                 ║")
        print("  ║  demo                — добавить демо-набор датчиков    ║")
        print("  ║  help                — показать справку                ║")
        print("  ║  quit                — выход                           ║")
        print("  ╚══════════════════════════════════════════════════════════╝")
        print()
        print("  Типы датчиков:")
        for key, preset in SENSOR_PRESETS.items():
            params = ", ".join(preset["params"].keys())
            print(f"    {key:<10} — {preset['description']} [{params}]")
        print()

    def _handle_command(self, cmd: str):
        parts = cmd.split()
        action = parts[0].lower()

        if action in ("add", "+"):
            if len(parts) < 3:
                print("  Использование: add <имя> <тип>")
                print(f"  Типы: {', '.join(SENSOR_PRESETS.keys())}")
                return
            name, preset = parts[1], parts[2]
            if preset not in SENSOR_PRESETS:
                print(f"  ✗ Неизвестный тип: {preset}")
                print(f"  Доступные типы: {', '.join(SENSOR_PRESETS.keys())}")
                return
            self.add_sensor(name, preset)

        elif action in ("rm", "del", "remove", "-"):
            if len(parts) < 2:
                print("  Использование: rm <имя>")
                return
            self.remove_sensor(parts[1])

        elif action == "pause":
            if len(parts) < 2:
                print("  Использование: pause <имя>")
                return
            self.pause_sensor(parts[1])

        elif action == "send":
            if len(parts) < 2:
                print("  Использование: send <имя>")
                return
            self.send_once(parts[1])

        elif action in ("list", "ls"):
            self.list_sensors()

        elif action == "demo":
            self._add_demo()

        elif action in ("help", "?"):
            self._print_help()

        elif action in ("quit", "exit", "q"):
            self.running = False

        else:
            print(f"  ✗ Неизвестная команда: {action}. Введите 'help'.")

    def _add_demo(self):
        """Add a demo set of sensors matching typical HomeSite setup."""
        demos = [
            ("tsboiler_s", "temp"),
            ("tsboiler_b", "temp"),
            ("tsrad_s", "temp"),
            ("tsrad_b", "temp"),
            ("tsfloor_s", "temp"),
            ("tsfloor_b", "temp"),
            ("clm_gost_th", "climate"),
            ("clm_kitchen_th", "climate"),
            ("clm_street_th", "climate"),
        ]
        print("\n  Добавление демо-набора датчиков:")
        for name, preset in demos:
            self.add_sensor(name, preset)
        print()


def main():
    parser = argparse.ArgumentParser(description="ESP32 Sensor Emulator for HomeSite")
    parser.add_argument("--host", default="127.0.0.1", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    args = parser.parse_args()

    emu = ESP32Emulator(args.host, args.port)
    emu.run()


if __name__ == "__main__":
    main()
