"""Port of the boiler controller firmware (firmware/esp32-homesite/src/boiler_logic.cpp).

Kept deliberately close to the C++ so the emulator reacts to settings exactly
like the real device: same update order, hysteresis, pulse-driven 3-way
valves, autofill lockout, interlocks applied last, same heartbeat fields.
Time is simulation seconds (``t``) instead of millis().
"""

from dataclasses import dataclass, field
from datetime import datetime

from .plant import RELAYS
from .settings import SETTINGS, defaults, is_valid

TEMP_INVALID = None

BOILER_HYSTERESIS = 2.0
IHB_HYSTERESIS = 2.0
AUTOFILL_MAX_S = 120.0
AUTOFILL_VALVE_TRAVEL_S = 15.0
AUTOFILL_HYSTERESIS = 0.1
VALVE_ADJUST_INTERVAL_S = 30.0
VALVE_DEADBAND = 1.0
VALVE_MAX_ERROR = 10.0
VALVE_MIN_PULSE_S = 1.0
VALVE_MAX_PULSE_S = 15.0
SENSOR_LOSS_CYCLES = 3
MIN_SUPPLY_TARGET = 20.0
OUTDOOR_TTL_S = 15 * 60

# PZA curves — same as backend app/services/pza.py and firmware pza_controller.cpp
OUTDOOR_POINTS = [20, 10, 0, -10, -20, -35]
RADIATOR_CURVES = [
    [20, 29, 38, 44, 50, 55],
    [20, 32.5, 45, 52.5, 60, 67],
    [20, 34, 48, 56, 64, 70],
    [20, 36.5, 53, 61.5, 70, 78],
    [20, 39, 58, 67, 76, 85],
]
FLOOR_CURVES = [
    [20, 22, 24, 26, 28, 29.5],
    [20, 23.5, 27, 29.5, 32, 34],
    [20, 23.5, 27, 30, 33, 36],
    [20, 24.5, 29, 32, 35, 38],
    [20, 25.5, 31, 34, 37, 40],
]


def interpolate(curve: list[float], outdoor: float) -> float:
    if outdoor >= OUTDOOR_POINTS[0]:
        return curve[0]
    if outdoor <= OUTDOOR_POINTS[-1]:
        return curve[-1]
    for i in range(len(OUTDOOR_POINTS) - 1):
        o0, o1 = OUTDOOR_POINTS[i], OUTDOOR_POINTS[i + 1]
        if o1 <= outdoor <= o0:
            return curve[i] + (o0 - outdoor) / (o0 - o1) * (curve[i + 1] - curve[i])
    return curve[0]


def in_schedule(now: datetime, days: str, start: str, end: str) -> bool:
    """Firmware NtpTime::isInSchedule — ISO weekday list, overnight windows."""
    if not days:
        return False
    if str(now.isoweekday()) not in days.split(","):
        return False
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    minutes = now.hour * 60 + now.minute
    s, e = sh * 60 + sm, eh * 60 + em
    return s <= minutes < e if s <= e else (minutes >= s or minutes < e)


@dataclass
class ValveState:
    drive_start: float = 0.0
    drive_s: float = 0.0
    last_adjust: float = -1e9
    opening: bool = False


@dataclass
class Controller:
    settings: dict[str, str] = field(default_factory=defaults)   # "NVS"
    autofill_fault: bool = False                                  # persisted flag

    relays: dict[str, bool] = field(default_factory=lambda: {r: False for r in RELAYS})
    outdoor: float | None = None
    outdoor_at: float = -1e9
    t: float = 0.0                       # seconds since boot

    boiler_auto_target: float = 0.0
    alm_active: bool = False
    ihb_heating: bool = False
    schedule_rad: bool = False
    schedule_floor: bool = False
    warning: bool = False
    critical: bool = False
    overtemp: bool = False
    boiler_sensor_missing: int = 0
    boiler_sensor_lost: bool = False

    autofill_active: bool = False
    autofill_closing: bool = False
    autofill_start: float = 0.0
    autofill_close_start: float = 0.0
    teh_delay_active: bool = False
    teh_delay_start: float = 0.0

    rad_valve: ValveState = field(default_factory=ValveState)
    floor_valve: ValveState = field(default_factory=ValveState)
    log: list[str] = field(default_factory=list)

    # -------------------------------------------------------------- settings
    def s(self, key: str) -> str:
        return self.settings.get(key, SETTINGS[key].default)

    def b(self, key: str) -> bool:
        return self.s(key) == "1"

    def f(self, key: str) -> float:
        return float(self.s(key))

    def on_setting(self, key: str, value: str) -> str:
        spec = SETTINGS.get(key)
        if spec is None:
            return "unknown_key"
        if not is_valid(spec, value):
            return "invalid_value"
        if spec.kind == "time":
            h, m = value.split(":")
            value = f"{int(h):02d}:{m}"
        self.settings[key] = value
        return "ok"

    def set_outdoor(self, temp: float) -> None:
        self.outdoor = temp
        self.outdoor_at = self.t

    def outdoor_fresh(self) -> bool:
        return self.outdoor is not None and self.t - self.outdoor_at < OUTDOOR_TTL_S

    def reset_autofill_fault(self) -> None:
        self.autofill_fault = False
        self._log("AUTOFILL: fault reset")

    def reboot(self) -> None:
        """ESP.restart(): RAM state lost, relays off, NVS (settings, fault flag) kept."""
        keep_settings, keep_fault = dict(self.settings), self.autofill_fault
        self.__init__(settings=keep_settings, autofill_fault=keep_fault)  # type: ignore[misc]

    def _log(self, msg: str) -> None:
        self.log.append(msg)
        del self.log[:-50]

    # -------------------------------------------------------------- PZA
    def rad_pza_target(self) -> float:
        if not self.b("heating_radiator_wbm") or not self.outdoor_fresh():
            return -1
        return interpolate(RADIATOR_CURVES[int(self.f("heating_radiator_curve")) - 1], self.outdoor)

    def floor_pza_target(self) -> float:
        if not self.b("heating_floorheating_wbm") or not self.outdoor_fresh():
            return -1
        return interpolate(FLOOR_CURVES[int(self.f("heating_floorheating_curve")) - 1], self.outdoor)

    def _circuit_target(self, prefix: str, pza: float, schedule: bool) -> float:
        manual = self.f(f"{prefix}_temp")
        t = pza if self.b(f"{prefix}_wbm") else manual
        if t < 0:
            t = manual
        if schedule:
            t += self.f(f"{prefix}_schedule_delta")
        return max(MIN_SUPPLY_TARGET, t)

    def radiator_target(self) -> float:
        """PZA or manual + night delta — used by the boiler target AND the valve."""
        return self._circuit_target("heating_radiator", self.rad_pza_target(), self.schedule_rad)

    def floor_target(self) -> float:
        return self._circuit_target("heating_floorheating", self.floor_pza_target(), self.schedule_floor)

    def ihb_target(self) -> float:
        ihb, alm = self.f("watersupply_ihb_temp"), self.f("watersupply_alm_temp")
        return alm if self.alm_active and alm > ihb else ihb

    # -------------------------------------------------------------- tick
    def tick(self, dt: float) -> None:
        self.t += dt
        for vs, o, c in ((self.rad_valve, "rad_open", "rad_close"), (self.floor_valve, "floor_open", "floor_close")):
            self._finish_pulse(vs, o, c)
        if self.autofill_closing and self.t - self.autofill_close_start >= AUTOFILL_VALVE_TRAVEL_S:
            self.relays["af_close"] = False
            self.autofill_closing = False
        if self.autofill_active and self.t - self.autofill_start > AUTOFILL_MAX_S:
            self._trip_autofill()

    def _finish_pulse(self, vs: ValveState, open_r: str, close_r: str) -> None:
        if vs.drive_s > 0 and self.t - vs.drive_start >= vs.drive_s:
            self.relays[open_r] = self.relays[close_r] = False
            vs.drive_s = 0

    # -------------------------------------------------------------- update
    def update(self, now: datetime, temps: dict[str, float], heating_pressure: float) -> None:
        self.schedule_rad = self.b("heating_radiator_schedule_enabled") and in_schedule(
            now, self.s("heating_radiator_schedule_days"),
            self.s("heating_radiator_schedule_start"), self.s("heating_radiator_schedule_end"))
        self.schedule_floor = self.b("heating_floorheating_schedule_enabled") and in_schedule(
            now, self.s("heating_floorheating_schedule_days"),
            self.s("heating_floorheating_schedule_start"), self.s("heating_floorheating_schedule_end"))

        if temps.get("tsboiler_s") is None:
            self.boiler_sensor_missing = min(255, self.boiler_sensor_missing + 1)
        else:
            self.boiler_sensor_missing = 0
        was_lost = self.boiler_sensor_lost
        self.boiler_sensor_lost = self.boiler_sensor_missing >= SENSOR_LOSS_CYCLES
        if self.boiler_sensor_lost and not was_lost:
            self._log("BOILER: SENSOR LOST")

        self._update_alm(now, temps)
        ihb = temps.get("tsihb_s")
        self.ihb_heating = ihb is not None and ihb < self.ihb_target()

        self._update_boiler(temps)
        self._update_pumps(temps)
        self._update_autofill(heating_pressure)
        self._update_teh(temps)
        self._update_valves(temps)
        self.relays["water_pump"] = self.b("watersupply_pump")
        self.relays["water_hot_pump"] = self.b("watersupply_pump_hot")
        self._apply_interlocks(temps)
        self._update_alarms(temps, heating_pressure)

    def _update_alm(self, now: datetime, temps: dict[str, float]) -> None:
        days = self.s("watersupply_alm_days")
        if not self.b("watersupply_ihb_alm_mode") or not days:
            self.alm_active = False
            return
        sh, sm = (int(x) for x in self.s("watersupply_alm_start_time").split(":"))
        total = sh * 60 + sm + int(self.f("watersupply_alm_duration"))
        end = f"{(total // 60) % 24:02d}:{total % 60:02d}"
        in_window = in_schedule(now, days, self.s("watersupply_alm_start_time"), end)
        ihb = temps.get("tsihb_s")
        active = in_window and ihb is not None and ihb < self.f("watersupply_alm_temp")
        if active and not self.alm_active:
            self._log("ALM: anti-legionella heating started")
        self.alm_active = active

    def _update_boiler(self, temps: dict[str, float]) -> None:
        bt = temps.get("tsboiler_s")
        max_temp = self.f("heating_boiler_max_temp")
        if bt is not None and bt >= max_temp:
            self.relays["boiler"] = False
            return
        if not self.b("heating_boiler_automode"):
            self.relays["boiler"] = self.b("heating_boiler_power")
            return
        if bt is None:
            return  # brief dropout — interlock handles a sustained loss
        target = 0.0
        if self.b("heating_radiator_pump"):
            target = max(target, self.radiator_target())
        if self.b("heating_floorheating_pump"):
            target = max(target, self.floor_target())
        if self.b("watersupply_ihb_automode") or self.b("watersupply_ihb_pump"):
            target = max(target, self.ihb_target())
        if target <= 0:
            target = self.f("heating_boiler_temp")
        target = min(target, max_temp)
        self.boiler_auto_target = target
        on = self.relays["boiler"]
        if not on and bt < target:
            self.relays["boiler"] = True
        elif on and bt >= target + BOILER_HYSTERESIS:
            self.relays["boiler"] = False

    def _update_pumps(self, temps: dict[str, float]) -> None:
        if self.b("watersupply_ihb_automode"):
            ihb = temps.get("tsihb_s")
            was = self.relays["ihb_pump"]
            if ihb is None:
                on = False
            elif not was and ihb < self.ihb_target():
                on = True
            elif was and ihb >= self.ihb_target() + IHB_HYSTERESIS:
                on = False
            else:
                on = was
        else:
            on = self.b("watersupply_ihb_pump")
        self.relays["ihb_pump"] = on

        rad = self.b("heating_radiator_pump")
        if self.b("heating_radiator_off_ihb") and self.ihb_heating and on:
            rad = False
        self.relays["rad_pump"] = rad
        floor = self.b("heating_floorheating_pump")
        if self.b("heating_floorheating_off_ihb") and self.ihb_heating and on:
            floor = False
        self.relays["floor_pump"] = floor

    def _close_autofill(self) -> None:
        self.relays["af_open"] = False
        self.relays["af_close"] = True
        self.autofill_active = False
        self.autofill_closing = True
        self.autofill_close_start = self.t

    def _trip_autofill(self) -> None:
        self._close_autofill()
        self.autofill_fault = True
        self._log("AUTOFILL: SAFETY TIMEOUT — valve closed, locked out until autofill_reset")

    def _update_autofill(self, pressure: float) -> None:
        if self.autofill_closing:
            return
        if not self.b("heating_autofill_enabled") or self.autofill_fault:
            if self.autofill_active:
                self._close_autofill()
            return
        p_min = self.f("heating_pressure_min")
        if self.autofill_active:
            if self.t - self.autofill_start > AUTOFILL_MAX_S:
                self._trip_autofill()
            elif pressure >= p_min + AUTOFILL_HYSTERESIS:
                self._close_autofill()
                self._log(f"AUTOFILL: pressure OK ({pressure:.2f} bar) — closing valve")
        elif 0.01 < pressure < p_min:
            self.relays["af_close"] = False
            self.relays["af_open"] = True
            self.autofill_active = True
            self.autofill_start = self.t
            self._log(f"AUTOFILL: low pressure ({pressure:.2f} bar) — opening valve")

    def _update_teh(self, temps: dict[str, float]) -> None:
        ihb = temps.get("tsihb_s")
        if ihb is not None and ihb >= self.ihb_target():
            self.relays["teh"] = False
            self.teh_delay_active = False
            return
        if not self.b("watersupply_ihb_teh_automode"):
            self.relays["teh"] = self.b("watersupply_ihb_teh_power")
            return
        if self.relays["boiler"] and self.relays["ihb_pump"]:
            self.relays["teh"] = False
            self.teh_delay_active = False
        elif self.ihb_heating:
            if not self.teh_delay_active:
                self.teh_delay_active = True
                self.teh_delay_start = self.t
            elif self.t - self.teh_delay_start >= self.f("watersupply_ihb_teh_heating_delay") * 60:
                self.relays["teh"] = True
        else:
            self.teh_delay_active = False
            self.relays["teh"] = False

    def _drive_valve(self, vs: ValveState, open_r: str, close_r: str, target: float, actual: float | None) -> None:
        self._finish_pulse(vs, open_r, close_r)
        if vs.drive_s > 0 or self.t - vs.last_adjust < VALVE_ADJUST_INTERVAL_S:
            return
        vs.last_adjust = self.t
        if target < 0 or actual is None:
            return
        error = target - actual
        if abs(error) <= VALVE_DEADBAND:
            return
        ratio = min(1.0, abs(error) / VALVE_MAX_ERROR)
        pulse = VALVE_MIN_PULSE_S + ratio * (VALVE_MAX_PULSE_S - VALVE_MIN_PULSE_S)
        opening = error > 0
        self.relays[open_r if opening else close_r] = True
        self.relays[close_r if opening else open_r] = False
        vs.drive_start, vs.drive_s, vs.opening = self.t, pulse, opening

    def _update_valves(self, temps: dict[str, float]) -> None:
        self._drive_valve(self.rad_valve, "rad_open", "rad_close", self.radiator_target(), temps.get("tsrad_s"))
        self._drive_valve(self.floor_valve, "floor_open", "floor_close", self.floor_target(), temps.get("tsfloor_s"))

    def _apply_interlocks(self, temps: dict[str, float]) -> None:
        bt = temps.get("tsboiler_s")
        self.overtemp = bt is not None and bt >= self.f("heating_boiler_max_temp")
        reason = None
        if self.overtemp:
            reason = "OVERTEMP"
        elif not self.b("heating_boiler_automode") and not self.b("heating_boiler_power"):
            reason = "MANUAL OFF"
        elif self.b("heating_boiler_automode") and self.boiler_sensor_lost:
            reason = "SENSOR LOST"
        if reason and self.relays["boiler"]:
            self.relays["boiler"] = False
            self._log(f"BOILER: INTERLOCK OFF ({reason})")
        if self.autofill_fault and self.relays["af_open"]:
            self._close_autofill()

    def _update_alarms(self, temps: dict[str, float], pressure: float) -> None:
        bt = temps.get("tsboiler_s")
        p_min, p_max = self.f("heating_pressure_min"), self.f("heating_pressure_max")
        max_temp = self.f("heating_boiler_max_temp")
        warning = critical = False
        if pressure > 0.01:
            if pressure < p_min or pressure > p_max:
                warning = True
            if pressure < p_min - 0.3 or pressure > p_max + 0.3:
                critical = True
        if bt is not None:
            warning |= bt >= max_temp - 5
            critical |= bt >= max_temp
        else:
            warning = True
        if (self.b("heating_radiator_pump") and temps.get("tsrad_s") is None) or (
            self.b("heating_floorheating_pump") and temps.get("tsfloor_s") is None
        ):
            warning = True
        if self.b("watersupply_ihb_automode") and temps.get("tsihb_s") is None:
            critical = True
        if self.boiler_sensor_lost or self.overtemp or self.autofill_fault:
            critical = True
        self.warning, self.critical = warning, critical
        self.relays["lamp_warning"], self.relays["lamp_critical"] = warning, critical

    # -------------------------------------------------------------- heartbeat
    def heartbeat(self, prs_heat: float | None, prs_water: float | None) -> dict:
        mask = sum(1 << i for i, r in enumerate(RELAYS) if self.relays[r])
        hb: dict = {
            "uptime": int(self.t),
            "free_heap": 182_000 + int(self.t) % 4096,
            "rad_wbm": self.b("heating_radiator_wbm"),
            "rad_curve": int(self.f("heating_radiator_curve")),
            "floor_wbm": self.b("heating_floorheating_wbm"),
            "floor_curve": int(self.f("heating_floorheating_curve")),
        }
        if self.outdoor_fresh():
            hb["outdoor"] = round(self.outdoor, 1)
        if prs_heat is not None:
            hb["prs_heat"] = round(prs_heat, 2)
        if prs_water is not None:
            hb["prs_water"] = round(prs_water, 2)
        hb.update({
            "relays": mask,
            "boiler_auto": self.b("heating_boiler_automode"),
            "boiler_auto_target": self.boiler_auto_target,
            "teh_auto": self.b("watersupply_ihb_teh_automode"),
            "alm_active": self.alm_active,
            "autofill_active": self.autofill_active,
            "autofill_closing": self.autofill_closing,
            "ihb_heating": self.ihb_heating,
            "schedule_rad": self.schedule_rad,
            "schedule_floor": self.schedule_floor,
            "warning": self.warning,
            "critical": self.critical,
            "rad_valve_driving": self.rad_valve.drive_s > 0,
            "floor_valve_driving": self.floor_valve.drive_s > 0,
            "ihb_target": self.ihb_target(),
            "rad_target": round(self.radiator_target(), 1),
            "floor_target": round(self.floor_target(), 1),
            "autofill_fault": self.autofill_fault,
            "boiler_sensor_lost": self.boiler_sensor_lost,
            "overtemp": self.overtemp,
        })
        return hb
