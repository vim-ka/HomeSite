"""Simulation core: plant + controller + sensor models. No MQTT here (testable)."""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .controller import Controller
from .plant import Draw, Plant

# Wired to boiler_unit (DS18B20 on pipes)
DS18B20 = [
    "tsboiler_s", "tsboiler_b", "tsrad_s", "tsrad_b", "tsfloor_s", "tsfloor_b",
    "tsihb_s", "tsihb_b", "tswatersupply_c", "tswatersupply_h",
]
# 433 MHz BL999 room sensors received by the RF gateway
CLIMATE = [
    "clm_chld_th", "clm_cab_th", "clm_sleep_th", "clm_gost_th",
    "clm_kitchen_th", "clm_boiler_th", "clm_garage_th", "clm_street_th",
]

MAX_STEP = 2.0            # s, physics integration step
DEFAULT_READ_INTERVAL = 10.0


def ds18b20(value: float, rng: random.Random) -> float:
    """12-bit DS18B20: 0.0625 °C steps, ±0.1 °C noise."""
    return round(round((value + rng.gauss(0, 0.05)) / 0.0625) * 0.0625, 2)


@dataclass
class Simulation:
    plant: Plant
    controller: Controller = field(default_factory=Controller)
    now: datetime = field(default_factory=lambda: datetime.now().astimezone())
    read_interval: float = DEFAULT_READ_INTERVAL
    prs_heating_name: str = "prs_heating"
    prs_water_name: str = "prs_water"
    local_outdoor: bool = False        # feed the controller the street sensor directly
    failed: set[str] = field(default_factory=set)
    offsets: dict[str, float] = field(default_factory=dict)   # "<sensor>:<tmp|hmt|prs>" → offset
    _since_read: float = 0.0
    _rng: random.Random = field(default_factory=lambda: random.Random(7), repr=False)

    # ------------------------------------------------------------- stepping
    def advance(self, seconds: float) -> None:
        remaining = seconds
        while remaining > 1e-9:
            dt = min(MAX_STEP, remaining)
            self.plant.step(dt, self.now, self.controller.relays)
            self.plant.update_rooms(dt, self.now)
            self.controller.tick(dt)
            self.now += timedelta(seconds=dt)
            remaining -= dt
            self._since_read += dt
            if self._since_read >= self.read_interval:
                self._since_read = 0.0
                self._control_cycle()

    def _control_cycle(self) -> None:
        if self.local_outdoor and "clm_street_th" not in self.failed:
            self.controller.set_outdoor(self.plant.room_local.get("clm_street_th", self.plant.outdoor(self.now)))
        temps = self.boiler_readings()
        pressure = self.heating_pressure_reading()
        self.controller.update(self.now, temps, pressure if pressure is not None else 0.0)

    def warmup(self, hours: float) -> None:
        """Run quietly so plant, valves and controller reach a consistent state."""
        start = self.now
        self.now -= timedelta(hours=hours)
        self.advance(hours * 3600)
        self.now = start

    # ------------------------------------------------------------- readings
    def _offset(self, name: str, code: str) -> float:
        return self.offsets.get(f"{name}:{code}", 0.0)

    def boiler_readings(self) -> dict[str, float]:
        return {
            name: ds18b20(self.plant.pipes[name], self._rng) + self._offset(name, "tmp")
            for name in DS18B20
            if name not in self.failed
        }

    def heating_pressure_reading(self) -> float | None:
        if self.prs_heating_name in self.failed:
            return None
        raw = self.plant.heating_pressure() + self._rng.gauss(0, 0.006)
        return round(max(0.0, raw) + self._offset(self.prs_heating_name, "prs"), 2)

    def water_pressure_reading(self) -> float | None:
        if self.prs_water_name in self.failed:
            return None
        raw = self.plant.mains + self._rng.gauss(0, 0.01)
        return round(max(0.0, raw) + self._offset(self.prs_water_name, "prs"), 2)

    def climate_reading(self, name: str) -> dict[str, float] | None:
        if name in self.failed or name not in self.plant.room_local:
            return None
        t = self.plant.room_local[name]
        rh = self.plant.room_humidity(self.now, {name: t})[name]
        return {
            "tmp": round(t + self._rng.gauss(0, 0.05) + self._offset(name, "tmp"), 1),
            "hmt": float(round(rh + self._rng.gauss(0, 0.4) + self._offset(name, "hmt"))),
        }

    # ------------------------------------------------------------- console helpers
    def start_draw(self, minutes: float, lpm: float) -> None:
        self.plant.draw_override = Draw(self.now, self.now + timedelta(minutes=minutes), lpm)

    def status(self) -> dict:
        p = self.plant
        c = self.controller
        return {
            "time": f"{self.now:%a %d.%m %H:%M:%S}",
            "outdoor": round(p.outdoor(self.now), 1),
            "house": round(p.t_house, 2),
            "garage": round(p.t_garage, 1),
            "boiler": round(p.t_boiler, 1),
            "burner_kw": round(p.burner, 1),
            "q_rad_kw": round(p.q_rad, 2),
            "q_floor_kw": round(p.q_floor, 2),
            "rad_valve": round(p.rad_valve, 2),
            "floor_valve": round(p.floor_valve, 2),
            "tank": round(p.t_tank, 1),
            "pressure": round(p.heating_pressure(), 3),
            "leak_bar_day": p.leak_bar_per_day,
            "autofill_valve": round(p.af_valve, 2),
            "mains": round(p.mains, 2),
            "draw_lpm": round(p.draw_lpm(self.now), 1),
            "relays_on": [r for r, on in c.relays.items() if on],
            "alarms": [k for k in ("warning", "critical", "overtemp", "boiler_sensor_lost", "autofill_fault") if getattr(c, k)],
            "failed": sorted(self.failed),
        }

    # ------------------------------------------------------------- persistence
    PLANT_FIELDS = (
        "outdoor_base", "leak_bar_per_day", "boiler_panel", "weather_drift", "t_house", "t_garage",
        "t_boiler", "t_tank", "rad_valve", "floor_valve", "q_rad", "q_floor", "charge", "moisture",
        "pipes", "room_local",
    )

    def save(self, path: Path) -> None:
        state = {
            "saved_at": self.now.isoformat(),
            "plant": {k: getattr(self.plant, k) for k in self.PLANT_FIELDS},
            "nvs": {"settings": self.controller.settings, "autofill_fault": self.controller.autofill_fault},
            "failed": sorted(self.failed),
            "offsets": self.offsets,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1))
        tmp.replace(path)

    def load(self, path: Path) -> bool:
        try:
            state = json.loads(path.read_text())
        except (OSError, ValueError):
            return False
        for k, v in state.get("plant", {}).items():
            if k in self.PLANT_FIELDS:
                setattr(self.plant, k, v)
        nvs = state.get("nvs", {})
        self.controller.settings.update(nvs.get("settings", {}))
        self.controller.autofill_fault = bool(nvs.get("autofill_fault", False))
        self.failed = set(state.get("failed", []))
        self.offsets = dict(state.get("offsets", {}))
        return True
