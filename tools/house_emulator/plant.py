"""Physical model of the house and the boiler room.

Lumped-parameter model, units: kW, kJ/K, °C, bar, seconds. Tuned so that at
−12 °C outside with radiators at 50 °C and floor heating at 30 °C the house
settles around 22 °C — "winter, the house is already warm". A −10/−5 °C night
setback on the supply lets it cool by ~1.5–2 °C overnight.

What is modelled:
- weather: winter base temperature, diurnal swing, slow random drift (fronts)
- house: one thermal mass (τ ≈ 64 h) + per-room offsets and local events
  (cooking, fireplace, sun, PC in the study), unheated garage
- boiler: water mass, burner modulating to its panel setpoint while the
  controller relay is on
- radiator / floor loops: pump + motorised 3-way mixing valve (90 s travel),
  heat emission ~ k·(mean water − room)
- DHW tank (IHB): coil from the boiler, electric heater (TEH), showers and
  kitchen draws, hot-water recirculation
- heating pressure: water charge minus a slow leak plus autofill, plus
  thermal expansion of the water; mains water pressure with draw dips
- indoor humidity from outdoor absolute humidity + moisture sources
"""

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# --- Relay names (same order/meaning as firmware RelayChannel) --------------
RELAYS = [
    "boiler", "rad_pump", "floor_pump", "ihb_pump", "water_pump", "water_hot_pump",
    "teh", "af_open", "af_close", "rad_open", "rad_close", "floor_open", "floor_close",
    "lamp_warning", "lamp_critical", "spare",
]

# --- Model constants ---------------------------------------------------------
HOUSE_C = 54_000.0        # kJ/K  (≈15 kWh/K, τ ≈ 64 h — masonry house)
HOUSE_UA = 0.235          # kW/K  envelope + ventilation
HOUSE_GAINS = 0.4         # kW    people, appliances
GARAGE_C = 8_000.0
GARAGE_UA_OUT = 0.08
GARAGE_UA_HOUSE = 0.05

BOILER_C = 520.0          # kJ/K  water + heat exchanger
BOILER_PMAX = 24.0        # kW
BOILER_PMIN = 7.0         # kW — burner can't modulate lower, it cycles on/off instead
BOILER_CYCLE_HYST = 4.0   # °C around the panel setpoint
BOILER_STANDBY = 0.15     # kW at 60 K above room
PRIMARY_FLOW = 1.2        # kW/K

RAD_K, RAD_FLOW = 0.26, 0.6        # kW/K emission, kW/K water flow
FLOOR_K, FLOOR_FLOW = 0.325, 0.65
COIL_K, COIL_FLOW, COIL_MAX = 0.7, 0.8, 25.0
EMITTER_TAU = 40 * 60              # s, radiators/screed keep emitting after pump stop

TANK_C = 200 * 4.19                # 200 l DHW tank
TANK_LOSS = 0.06                   # kW at 35 K above room
TEH_POWER = 2.0                    # kW
COLD_WATER = 6.5                   # °C, winter mains / well
TAP_TEMP = 40.0                    # showers mix to 40 °C

VALVE_TRAVEL = 90.0                # s full stroke, 3-way valves
AUTOFILL_TRAVEL = 15.0             # s, ball valve
AUTOFILL_RATE = 0.004              # bar/s at fully open valve
EXPANSION = 0.005                  # bar/K of mean system water temperature
MAINS_PRESSURE = 3.0               # bar

PIPE_TAU_FLOW = 45.0               # s, pipe sensor response with flow
PIPE_TAU_STILL = 20 * 60.0         # s, pipe cooling to room air without flow


def _relax(value: float, target: float, dt: float, tau: float) -> float:
    return target + (value - target) * math.exp(-dt / tau)


def abs_humidity(temp: float, rh: float) -> float:
    """g/m³ (Magnus)."""
    return 6.112 * math.exp(17.67 * temp / (temp + 243.5)) * rh * 2.1674 / (273.15 + temp)


def rel_humidity(temp: float, ah: float) -> float:
    return 100.0 * ah / abs_humidity(temp, 100.0)


@dataclass
class Draw:
    start: datetime
    end: datetime
    lpm: float                     # litres per minute at the tap


@dataclass
class DayPlan:
    """Household routine for one day (generated per date, deterministic per seed)."""

    draws: list[Draw] = field(default_factory=list)
    cooking: list[tuple[datetime, datetime]] = field(default_factory=list)
    fireplace: tuple[datetime, datetime] | None = None
    showers_until: list[datetime] = field(default_factory=list)


def make_day_plan(day: datetime, seed: int) -> DayPlan:
    rng = random.Random(f"{seed}-{day:%Y-%m-%d}")
    base = day.replace(hour=0, minute=0, second=0, microsecond=0)
    weekend = day.isoweekday() >= 6
    plan = DayPlan()

    def at(hours: float) -> datetime:
        return base + timedelta(hours=hours)

    # Showers: morning (later on weekends) and evening
    morning = 8.2 if weekend else 6.8
    for start in (morning + rng.uniform(0, 0.8), 20.5 + rng.uniform(0, 1.0), 21.8 + rng.uniform(0, 1.0)):
        if rng.random() < 0.85:
            minutes = rng.uniform(7, 13)
            s = at(start)
            plan.draws.append(Draw(s, s + timedelta(minutes=minutes), rng.uniform(6, 8)))
            plan.showers_until.append(s + timedelta(minutes=minutes))
    # Kitchen / washbasin: short small draws through the day
    for _ in range(rng.randint(6, 12)):
        s = at(rng.uniform(7, 23))
        plan.draws.append(Draw(s, s + timedelta(minutes=rng.uniform(0.5, 3)), rng.uniform(2, 4)))
    # Cooking
    meals = [(7.3, 0.6), (18.5, 1.0)] + ([(13.0, 0.8)] if weekend else [])
    for start, dur in meals:
        s = at(start + rng.uniform(-0.3, 0.3))
        plan.cooking.append((s, s + timedelta(hours=dur)))
    # Fireplace on some evenings, mostly weekends
    if rng.random() < (0.5 if day.isoweekday() >= 5 else 0.1):
        s = at(19 + rng.uniform(0, 1.5))
        plan.fireplace = (s, s + timedelta(hours=rng.uniform(2, 3.5)))
    return plan


@dataclass
class Plant:
    seed: int = 1
    outdoor_base: float = -12.0
    leak_bar_per_day: float = 0.3
    boiler_panel: float = 75.0         # boiler's own thermostat (front panel)

    # --- state (warm start: winter evening, house heated) ---
    weather_drift: float = 0.0
    t_house: float = 22.3
    t_garage: float = 2.0
    t_boiler: float = 70.0
    t_tank: float = 54.0
    rad_valve: float = 0.45
    floor_valve: float = 0.35
    q_rad: float = 5.9                 # kW currently emitted into the house
    q_floor: float = 1.9
    af_valve: float = 0.0
    charge: float = 1.35               # bar at 20 °C water
    moisture: float = 3.5              # g/m³ indoor moisture excess
    burner: float = 0.0                # kW
    flame: bool = True
    burner_noise: float = 0.0          # kW, slow gas-pressure / modulation drift
    pipes: dict[str, float] = field(default_factory=dict)
    room_local: dict[str, float] = field(default_factory=dict)
    mains: float = MAINS_PRESSURE

    # Manual overrides from the console
    draw_override: Draw | None = None
    _plans: dict[str, DayPlan] = field(default_factory=dict, repr=False)
    _rng: random.Random = field(default_factory=random.Random, repr=False)

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)
        if not self.pipes:
            self.pipes = {
                "tsboiler_s": 70.0, "tsboiler_b": 63.5,
                "tsrad_s": 50.0, "tsrad_b": 40.2,
                "tsfloor_s": 30.0, "tsfloor_b": 27.1,
                "tsihb_s": 54.0, "tsihb_b": 24.0,
                "tswatersupply_c": 14.0, "tswatersupply_h": 49.0,
            }

    # ------------------------------------------------------------------ weather
    def outdoor(self, now: datetime) -> float:
        hour = now.hour + now.minute / 60
        diurnal = 4.0 * math.sin(2 * math.pi * (hour - 9) / 24)  # min ≈ 03:00, max ≈ 15:00
        return self.outdoor_base + diurnal + self.weather_drift

    def outdoor_rh(self, now: datetime) -> float:
        hour = now.hour + now.minute / 60
        return max(60.0, min(97.0, 86.0 - 8.0 * math.sin(2 * math.pi * (hour - 9) / 24)))

    def sun(self, now: datetime) -> float:
        """0..1 low winter sun, 10:00–15:00."""
        hour = now.hour + now.minute / 60
        return max(0.0, math.sin(math.pi * (hour - 10) / 5)) if 10 <= hour <= 15 else 0.0

    # ------------------------------------------------------------------ routine
    def plan(self, now: datetime) -> DayPlan:
        key = f"{now:%Y-%m-%d}"
        if key not in self._plans:
            self._plans = {k: v for k, v in self._plans.items() if k >= f"{now - timedelta(days=1):%Y-%m-%d}"}
            self._plans[key] = make_day_plan(now, self.seed)
        return self._plans[key]

    def draw_lpm(self, now: datetime) -> float:
        lpm = sum(d.lpm for d in self.plan(now).draws if d.start <= now < d.end)
        if self.draw_override and self.draw_override.start <= now < self.draw_override.end:
            lpm += self.draw_override.lpm
        return lpm

    def cooking(self, now: datetime) -> bool:
        return any(s <= now < e for s, e in self.plan(now).cooking)

    def fireplace(self, now: datetime) -> bool:
        fp = self.plan(now).fireplace
        return fp is not None and fp[0] <= now < fp[1]

    def shower_recent(self, now: datetime) -> bool:
        return any(now - timedelta(hours=1) < t <= now for t in self.plan(now).showers_until)

    # ------------------------------------------------------------------ helpers
    @property
    def boiler_room(self) -> float:
        return self.t_house - 1.0 + 3.0 * min(1.0, self.burner / BOILER_PMAX) + 0.03 * (self.t_boiler - 60)

    def heating_pressure(self) -> float:
        t_rad = (self.pipes["tsrad_s"] + self.pipes["tsrad_b"]) / 2
        t_floor = (self.pipes["tsfloor_s"] + self.pipes["tsfloor_b"]) / 2
        t_sys = 0.25 * self.t_boiler + 0.45 * t_rad + 0.30 * t_floor
        return max(0.0, self.charge + EXPANSION * (t_sys - 20.0))

    # ------------------------------------------------------------------ step
    def step(self, dt: float, now: datetime, relays: dict[str, bool]) -> None:
        # Weather drift: Ornstein-Uhlenbeck, τ 6 h, σ ≈ 2.5 °C
        tau = 6 * 3600
        self.weather_drift += -self.weather_drift / tau * dt + 0.024 * math.sqrt(dt) * self._rng.gauss(0, 1)
        t_out = self.outdoor(now)
        room = self.boiler_room

        # 3-way valves: motors driven by the controller's open/close relays
        for name, open_r, close_r in (("rad_valve", "rad_open", "rad_close"), ("floor_valve", "floor_open", "floor_close")):
            pos = getattr(self, name)
            if relays[open_r] and not relays[close_r]:
                pos += dt / VALVE_TRAVEL
            elif relays[close_r] and not relays[open_r]:
                pos -= dt / VALVE_TRAVEL
            setattr(self, name, min(1.0, max(0.0, pos)))

        # Emitter loops (radiators, floor)
        q_boiler_load = 0.0
        loops = (
            ("rad", "rad_pump", self.rad_valve, RAD_K, RAD_FLOW, "q_rad"),
            ("floor", "floor_pump", self.floor_valve, FLOOR_K, FLOOR_FLOW, "q_floor"),
        )
        for prefix, pump, valve, k, flow, q_attr in loops:
            s_key, b_key = f"ts{prefix}_s", f"ts{prefix}_b"
            if relays[pump]:
                a = k / (1 + k / (2 * flow))
                ratio = a / flow
                v = max(valve, 1e-3)
                supply = (v * self.t_boiler + (1 - v) * ratio * self.t_house) / (v + (1 - v) * ratio)
                q = max(0.0, a * (supply - self.t_house))
                ret = supply - q / flow
                setattr(self, q_attr, _relax(getattr(self, q_attr), q, dt, 120.0))
                self.pipes[s_key] = _relax(self.pipes[s_key], supply, dt, PIPE_TAU_FLOW)
                self.pipes[b_key] = _relax(self.pipes[b_key], ret, dt, PIPE_TAU_FLOW)
                q_boiler_load += q
            else:
                setattr(self, q_attr, getattr(self, q_attr) * math.exp(-dt / EMITTER_TAU))
                self.pipes[s_key] = _relax(self.pipes[s_key], room, dt, PIPE_TAU_STILL)
                self.pipes[b_key] = _relax(self.pipes[b_key], room, dt, PIPE_TAU_STILL)

        # DHW tank coil. The firmware treats tsihb_s as the tank temperature
        # (pump, TEH and anti-legionella regulate on it), so it sits in the tank
        # sleeve; tsihb_b is on the coil return pipe.
        q_ihb = 0.0
        if relays["ihb_pump"]:
            q_ihb = min(COIL_MAX, max(0.0, COIL_K * (self.t_boiler - self.t_tank)))
            self.pipes["tsihb_b"] = _relax(self.pipes["tsihb_b"], self.t_boiler - q_ihb / COIL_FLOW, dt, PIPE_TAU_FLOW)
        else:
            self.pipes["tsihb_b"] = _relax(self.pipes["tsihb_b"], room, dt, PIPE_TAU_STILL)
        self.pipes["tsihb_s"] = _relax(self.pipes["tsihb_s"], self.t_tank, dt, 90.0)
        q_boiler_load += q_ihb

        # Hot water draws (no cold-water pump → no water at the taps)
        lpm = self.draw_lpm(now) if relays["water_pump"] else 0.0
        q_draw = 0.0
        if lpm > 0:
            hot_frac = 1.0 if self.t_tank <= TAP_TEMP else (TAP_TEMP - COLD_WATER) / (self.t_tank - COLD_WATER)
            q_draw = lpm / 60 * hot_frac * 4.19 * (self.t_tank - COLD_WATER)
        teh = TEH_POWER if relays["teh"] else 0.0
        loss = TANK_LOSS * (self.t_tank - room) / 35
        self.t_tank += (q_ihb + teh - loss - q_draw) / TANK_C * dt

        hot_target = self.t_tank - 1.5 if lpm > 0 else (self.t_tank - 4.0 if relays["water_hot_pump"] else room)
        self.pipes["tswatersupply_h"] = _relax(
            self.pipes["tswatersupply_h"], hot_target, dt, PIPE_TAU_FLOW if hot_target != room else PIPE_TAU_STILL
        )
        cold_target = COLD_WATER + 0.5 if lpm > 0 else room
        self.pipes["tswatersupply_c"] = _relax(
            self.pipes["tswatersupply_c"], cold_target, dt, PIPE_TAU_FLOW * 2 if lpm > 0 else 2 * PIPE_TAU_STILL
        )

        # Boiler: burner modulates to its panel setpoint while the relay is on;
        # below minimum modulation it cycles (flame off above panel+hyst,
        # re-ignites below panel−hyst) — the familiar boiler temperature sawtooth
        if relays["boiler"]:
            if self.flame and self.t_boiler >= self.boiler_panel + BOILER_CYCLE_HYST:
                self.flame = False
            elif not self.flame and self.t_boiler <= self.boiler_panel - BOILER_CYCLE_HYST:
                self.flame = True
            # soft regulation + slow gas-pressure drift (OU, τ 5 min, σ ≈ 2 kW) → ±1 °C wander
            self.burner_noise += -self.burner_noise / 300 * dt + 0.16 * math.sqrt(dt) * self._rng.gauss(0, 1)
            demand = 0.7 * (self.boiler_panel - self.t_boiler) + q_boiler_load + self.burner_noise
            power = min(BOILER_PMAX, max(BOILER_PMIN, demand)) if self.flame else 0.0
            self.burner = _relax(self.burner, power, dt, 20.0)
        else:
            self.flame = True
            self.burner = _relax(self.burner, 0.0, dt, 10.0)
        standby = BOILER_STANDBY * (self.t_boiler - room) / 60
        self.t_boiler += (self.burner - q_boiler_load - standby) / BOILER_C * dt
        any_flow = relays["rad_pump"] or relays["floor_pump"] or relays["ihb_pump"]
        self.pipes["tsboiler_s"] = _relax(self.pipes["tsboiler_s"], self.t_boiler, dt, PIPE_TAU_FLOW)
        ret = self.t_boiler - q_boiler_load / PRIMARY_FLOW if any_flow else self.t_boiler - 1.0
        self.pipes["tsboiler_b"] = _relax(self.pipes["tsboiler_b"], ret, dt, PIPE_TAU_FLOW if any_flow else PIPE_TAU_STILL)

        # House and garage
        gains = HOUSE_GAINS + (1.5 if self.cooking(now) else 0.0) + (3.0 if self.fireplace(now) else 0.0)
        gains += 1.2 * self.sun(now)
        q_loss = HOUSE_UA * (self.t_house - t_out) + GARAGE_UA_HOUSE * (self.t_house - self.t_garage)
        self.t_house += (self.q_rad + self.q_floor + gains - q_loss) / HOUSE_C * dt
        q_garage = GARAGE_UA_OUT * (t_out - self.t_garage) + GARAGE_UA_HOUSE * (self.t_house - self.t_garage)
        self.t_garage += q_garage / GARAGE_C * dt

        # Indoor moisture excess: people/plants baseline, cooking and showers add, ventilation removes
        source = 3.5 + (3.0 if self.cooking(now) else 0.0) + (2.5 if self.shower_recent(now) else 0.0)
        self.moisture = _relax(self.moisture, source, dt, 90 * 60)

        # Heating circuit water: slow leak, autofill ball valve
        if relays["af_open"] and not relays["af_close"]:
            self.af_valve = min(1.0, self.af_valve + dt / AUTOFILL_TRAVEL)
        elif relays["af_close"] and not relays["af_open"]:
            self.af_valve = max(0.0, self.af_valve - dt / AUTOFILL_TRAVEL)
        if self.heating_pressure() > 0:
            self.charge -= self.leak_bar_per_day / 86400 * dt
        if self.af_valve > 0 and self.mains > self.heating_pressure():
            self.charge += AUTOFILL_RATE * self.af_valve * dt

        # Mains / well pressure: dips while water is drawn
        if relays["water_pump"]:
            mains_target = MAINS_PRESSURE - 0.06 * lpm + 0.08 * math.sin(now.timestamp() / 900)
        else:
            mains_target = 0.2
        self.mains = _relax(self.mains, mains_target, dt, 20.0)

    # ------------------------------------------------------------------ rooms
    def room_temps(self, now: datetime) -> dict[str, float]:
        """True air temperature per climate sensor."""
        hour = now.hour + now.minute / 60
        cooking = self.cooking(now)
        fire = self.fireplace(now)
        sun = self.sun(now)
        targets = {
            "clm_chld_th": self.t_house + 0.3 + 0.4 * sun,
            "clm_cab_th": self.t_house - 0.3 + (0.6 if 9 <= hour < 19 and now.isoweekday() <= 5 else 0.0),
            "clm_sleep_th": self.t_house - 0.9 + 0.3 * sun,
            "clm_gost_th": self.t_house + 0.2 + (2.2 if fire else 0.0) + 0.6 * sun,
            "clm_kitchen_th": self.t_house + 0.4 + (1.8 if cooking else 0.0),
            "clm_boiler_th": self.boiler_room,
            "clm_garage_th": self.t_garage,
            "clm_street_th": self.outdoor(now) + 0.8 + 2.5 * sun,  # balcony: a bit warmer, sunlit at noon
        }
        return targets

    def update_rooms(self, dt: float, now: datetime) -> dict[str, float]:
        """Rooms follow their targets with local inertia (τ 25 min)."""
        targets = self.room_temps(now)
        for name, target in targets.items():
            current = self.room_local.get(name, target)
            tau = 10 * 60 if name == "clm_street_th" else 25 * 60
            self.room_local[name] = _relax(current, target, dt, tau)
        return dict(self.room_local)

    def room_humidity(self, now: datetime, temps: dict[str, float]) -> dict[str, float]:
        ah_out = abs_humidity(self.outdoor(now), self.outdoor_rh(now))
        cooking = self.cooking(now)
        out = {}
        for name, t in temps.items():
            if name == "clm_street_th":
                ah = ah_out
            elif name == "clm_garage_th":
                ah = ah_out + 0.8
            else:
                extra = self.moisture
                if name == "clm_kitchen_th" and cooking:
                    extra += 3.0
                if name == "clm_boiler_th":
                    extra -= 1.0
                ah = ah_out + max(0.0, extra)
            out[name] = max(10.0, min(99.0, rel_humidity(t, ah)))
        return out
