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
VALVE_SETTLE_S = 30.0  # after the circuit pump starts, the sensor first sees standing water
SENSOR_LOSS_CYCLES = 3
MIN_SUPPLY_TARGET = 20.0
# The tank temperature: the sensor in the tank's upper sleeve («Горячее водоснабжение»). tsihb_s / tsihb_b are the
# loading pipes (coil supply / return) — a loading pipe cools when the pump stops, it must never stand for the tank.
TANK_SENSOR = "tswatersupply_h"
OUTDOOR_TTL_S = 15 * 60
INDOOR_TTL_S = 10 * 60             # the backend forwards the house average every ~30 s
ROOM_CORRECTION_MAX = 10.0         # room correction of the radiator curve, ± °C (the floor: half, ± 5)
BOILER_MIN_ON_S = 5 * 60           # auto mode: no short burner cycles
BOILER_MIN_OFF_S = 5 * 60

# Safety rules from the alarm review (2026-09)
PRESSURE_ZERO_BAR = 0.05           # configured sensor below this: empty system or broken sensor
BOILER_TARGET_MARGIN = 5.0         # auto target stays max - margin - hysteresis: regulation, never the trip
TEH_BOILER_MARGIN = 5.0            # the boiler heats the tank only if its supply is this much hotter
FROST_ENTER = 7.0                  # any water temperature below → frost protection
FROST_EXIT = 15.0                  # all back above → normal control
SENSOR_LOST_MILD_OUTDOOR = 5.0     # boiler sensor lost: switch off only when it's this warm outside
NO_HEAT_AFTER_S = 30 * 60          # boiler on this long, still far below target and not warming up …
NO_HEAT_WINDOW_S = 15 * 60         # … by at least NO_HEAT_MIN_RISE over this window
NO_HEAT_MIN_RISE = 2.0
NO_HEAT_GAP = 10.0
NO_HEAT_MANUAL_BELOW = 30.0        # manual mode: the boiler's own thermostat decides — only a cold supply counts
WELL_MIN_BAR = 0.5                 # well pump on, water pressure below this …
WELL_GRACE_S = 60.0                # … this long → dry run
WELL_RETRY_S = 30 * 60
WELL_MAX_TRIES = 3
ALM_HOLD_S = 10 * 60
MUTE_FORGET_S = 5 * 60             # a muted cause gone this long is forgotten: its return sounds again
PRESSURE_CRIT_HYSTERESIS = 0.05               # anti-legionella counts only after the tank held the temperature this long

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
    pump_since: float | None = None  # when the circuit pump started (None = pump off)


@dataclass
class Controller:
    settings: dict[str, str] = field(default_factory=defaults)   # "NVS"
    autofill_fault: bool = False                                  # persisted flag

    relays: dict[str, bool] = field(default_factory=lambda: {r: False for r in RELAYS})
    outdoor: float | None = None
    outdoor_at: float = -1e9
    outdoor_smooth: float | None = None        # what the weather curves see (low-pass of the street reading)
    indoor: float | None = None
    indoor_at: float = -1e9
    boiler_last: bool = False                  # boiler relay as the last cycle left it …
    boiler_changed_at: float | None = None     # … and since when (None: not switched since boot)
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
    ihb_sensor_missing: int = 0
    ihb_sensor_lost: bool = False
    floor_sensor_missing: int = 0
    floor_sensor_lost: bool = False
    pressure_zero: bool = False
    frost_protect: bool = False
    boiler_no_heat: bool = False
    boiler_on_since: float | None = None
    no_heat_check: tuple[float, float] | None = None   # (t, supply) at the start of the current window
    no_heat_stalled: bool = False
    well_low_since: float | None = None
    well_waiting: bool = False
    well_retry_at: float = 0.0
    well_failures: int = 0
    well_locked: bool = False
    well_dry: bool = False
    alm_hold_since: float | None = None
    alm_done: bool = False              # this window's disinfection is complete
    alm_in_window: bool = False
    alm_last: str = ""                  # "", "ok", "failed" — result of the last window
    reset_reason: str = "poweron"
    critical_causes: set[str] = field(default_factory=set)
    muted_causes: set[str] = field(default_factory=set)
    cause_seen_at: dict[str, float] = field(default_factory=dict)

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
        """A street reading. The curves follow it through a first-order low-pass with the building's time
        constant (kotelna.tk: building inertia is hours; TAC default 4 h); a fresh start after a gap."""
        tau_s = self.f("heating_pza_outdoor_tau_h") * 3600
        gap = self.t - self.outdoor_at
        if self.outdoor_smooth is None or tau_s <= 0 or gap >= OUTDOOR_TTL_S:
            self.outdoor_smooth = temp
        else:
            self.outdoor_smooth += gap / (tau_s + gap) * (temp - self.outdoor_smooth)
        self.outdoor = temp
        self.outdoor_at = self.t

    def outdoor_pza(self) -> float | None:
        return self.outdoor_smooth if self.outdoor_fresh() else None

    def outdoor_fresh(self) -> bool:
        return self.outdoor is not None and self.t - self.outdoor_at < OUTDOOR_TTL_S

    def set_indoor(self, temp: float) -> None:
        """indoor_temp telemetry: the house average the backend forwards."""
        self.indoor = temp
        self.indoor_at = self.t

    def room_correction(self, scale: float, limit: float, night: bool = False) -> float:
        """Weather curve + factor × (room target − house); none without fresh indoor data.
        During the circuit's night setback the house cools on purpose: the correction may only lower the supply."""
        factor = self.f("heating_room_factor")
        if factor <= 0 or self.indoor is None or self.t - self.indoor_at >= INDOOR_TTL_S:
            return 0.0
        corr = max(-limit, min(limit, factor * (self.f("heating_room_temp") - self.indoor) * scale))
        return min(corr, 0.0) if night else corr

    def reset_well(self) -> None:
        """well_reset command: clear the dry-run latch; the pump tries again right away."""
        self.well_locked = self.well_waiting = self.well_dry = False
        self.well_failures, self.well_low_since = 0, None
        self._log("WELL: dry-run lock reset")

    def reset_autofill_fault(self) -> None:
        self.autofill_fault = False
        self._log("AUTOFILL: fault reset")

    def reboot(self) -> None:
        """ESP.restart(): RAM state lost, relays off, NVS (settings, fault flag) kept."""
        keep_settings, keep_fault = dict(self.settings), self.autofill_fault
        self.__init__(settings=keep_settings, autofill_fault=keep_fault)  # type: ignore[misc]
        self.reset_reason = "software"

    def _log(self, msg: str) -> None:
        self.log.append(msg)
        del self.log[:-50]

    def _recirc_window(self, now: datetime) -> bool:
        """Recirculation schedule: only in the morning / evening window (every day); no schedule — always."""
        if not self.b("watersupply_recirc_schedule_enabled"):
            return True
        every_day = "1,2,3,4,5,6,7"
        return any(in_schedule(now, every_day, self.s(f"watersupply_recirc_{w}_start"), self.s(f"watersupply_recirc_{w}_end"))
                   for w in ("morning", "evening"))

    # -------------------------------------------------------------- PZA
    def rad_pza_target(self) -> float:
        if not self.b("heating_radiator_wbm") or not self.outdoor_fresh():
            return -1
        return interpolate(RADIATOR_CURVES[int(self.f("heating_radiator_curve")) - 1], self.outdoor_smooth)

    def floor_pza_target(self) -> float:
        if not self.b("heating_floorheating_wbm") or not self.outdoor_fresh():
            return -1
        return interpolate(FLOOR_CURVES[int(self.f("heating_floorheating_curve")) - 1], self.outdoor_smooth)

    def _circuit_target(self, prefix: str, pza: float, schedule: bool, room: float = 0.0) -> float:
        manual = self.f(f"{prefix}_temp")
        t = pza + room if self.b(f"{prefix}_wbm") and pza >= 0 else manual
        if schedule:
            t += self.f(f"{prefix}_schedule_delta")
        return max(MIN_SUPPLY_TARGET, t)

    def radiator_target(self) -> float:
        """PZA or manual + night delta — used by the boiler target AND the valve."""
        return self._circuit_target("heating_radiator", self.rad_pza_target(), self.schedule_rad,
                                    self.room_correction(1.0, ROOM_CORRECTION_MAX, self.schedule_rad))

    def floor_target(self) -> float:
        return self._circuit_target("heating_floorheating", self.floor_pza_target(), self.schedule_floor,
                                    self.room_correction(0.5, ROOM_CORRECTION_MAX / 2, self.schedule_floor))

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
    def update(self, now: datetime, temps: dict[str, float], heating_pressure: float | None,
               water_pressure: float | None = None) -> None:
        """Pressures are None when the sensor isn't configured (firmware: NAN)."""
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

        if temps.get(TANK_SENSOR) is None:
            self.ihb_sensor_missing = min(255, self.ihb_sensor_missing + 1)
        else:
            self.ihb_sensor_missing = 0
        self.ihb_sensor_lost = self.ihb_sensor_missing >= SENSOR_LOSS_CYCLES
        if temps.get("tsfloor_s") is None:
            self.floor_sensor_missing = min(255, self.floor_sensor_missing + 1)
        else:
            self.floor_sensor_missing = 0
        self.floor_sensor_lost = self.floor_sensor_missing >= SENSOR_LOSS_CYCLES
        self.pressure_zero = heating_pressure is not None and heating_pressure < PRESSURE_ZERO_BAR
        self._update_frost(temps)

        self._update_alm(now, temps)
        ihb = temps.get(TANK_SENSOR)
        self.ihb_heating = ihb is not None and ihb < self.ihb_target()

        self._update_boiler(temps)
        self._update_pumps(temps)
        self._update_autofill(heating_pressure)
        self._update_teh(temps)
        self._update_valves(temps)
        self._update_well(water_pressure)
        self.relays["water_hot_pump"] = self.b("watersupply_pump_hot") and self._recirc_window(now)
        self._apply_interlocks(temps)
        self._update_no_heat(temps)
        self._update_alarms(temps, heating_pressure)

    def _update_frost(self, temps: dict[str, float]) -> None:
        """Water in the boiler or the circuits near freezing: heat regardless of manual OFF."""
        vals = [temps[k] for k in ("tsboiler_s", "tsrad_s", "tsfloor_s") if temps.get(k) is not None]
        if not vals:
            return
        if not self.frost_protect and min(vals) < FROST_ENTER:
            self.frost_protect = True
            self._log(f"FROST: protection ON ({min(vals):.1f} °C)")
        elif self.frost_protect and min(vals) >= FROST_EXIT:
            self.frost_protect = False
            self._log("FROST: protection OFF")

    def _mild_outside(self) -> bool:
        return self.outdoor_fresh() and self.outdoor >= SENSOR_LOST_MILD_OUTDOOR

    def _boiler_target(self) -> float:
        return self.boiler_auto_target if self.b("heating_boiler_automode") else self.f("heating_boiler_temp")

    def _update_no_heat(self, temps: dict[str, float]) -> None:
        """Boiler asked to heat for a long time, supply far below target and not rising: burner lockout, no gas."""
        bt = temps.get("tsboiler_s")
        if not self.relays["boiler"] or bt is None:
            self.boiler_on_since = self.no_heat_check = None
            self.no_heat_stalled = self.boiler_no_heat = False
            return
        if self.boiler_on_since is None:
            self.boiler_on_since, self.no_heat_check = self.t, (self.t, bt)
        cold = (bt < self._boiler_target() - NO_HEAT_GAP if self.b("heating_boiler_automode")
                else bt < NO_HEAT_MANUAL_BELOW)
        if not cold:
            self.no_heat_check, self.no_heat_stalled, self.boiler_no_heat = (self.t, bt), False, False
            return
        t0, bt0 = self.no_heat_check  # type: ignore[misc]
        if self.t - t0 >= NO_HEAT_WINDOW_S:
            self.no_heat_stalled = bt - bt0 < NO_HEAT_MIN_RISE
            self.no_heat_check = (self.t, bt)
        was = self.boiler_no_heat
        self.boiler_no_heat = self.t - self.boiler_on_since >= NO_HEAT_AFTER_S and self.no_heat_stalled
        if self.boiler_no_heat and not was:
            self._log(f"BOILER: NO HEAT (supply {bt:.1f} °C)")

    def _update_well(self, water: float | None) -> None:
        """Dry-run protection: no pressure with the pump on → stop, retry later, latch after repeated failures."""
        if not self.b("watersupply_pump"):
            self.relays["water_pump"] = False
            self.well_low_since, self.well_waiting, self.well_failures, self.well_locked = None, False, 0, False
            self.well_dry = False
            return
        if water is None:
            self.relays["water_pump"] = True
            self.well_low_since, self.well_dry = None, False
            return
        if self.well_locked or (self.well_waiting and self.t < self.well_retry_at):
            self.relays["water_pump"] = False
            return
        if self.well_waiting:  # retry: a fresh grace period
            self.well_waiting, self.well_low_since = False, None
        self.relays["water_pump"] = True
        if water < WELL_MIN_BAR:
            if self.well_low_since is None:
                self.well_low_since = self.t
            if self.t - self.well_low_since >= WELL_GRACE_S:
                self.relays["water_pump"] = False
                self.well_low_since = None
                self.well_failures += 1
                if self.well_failures >= WELL_MAX_TRIES:
                    self.well_locked = True
                    self._log("WELL: dry run — pump locked until switched off and on")
                else:
                    self.well_waiting, self.well_retry_at = True, self.t + WELL_RETRY_S
                    self._log("WELL: dry run — pump stopped, retry in 30 min")
        else:
            self.well_low_since, self.well_failures = None, 0
        self.well_dry = self.well_waiting or self.well_locked

    def _update_alm(self, now: datetime, temps: dict[str, float]) -> None:
        """Firmware updateAntiLegionella: raise the tank target in the window until the tank has HELD
        the temperature for ALM_HOLD_S; report the window's result (alm_last)."""
        days = self.s("watersupply_alm_days")
        if not self.b("watersupply_ihb_alm_mode") or not days:
            # switched off: no cycle, and no stale "failed" from a window that no longer matters
            self.alm_active = self.alm_in_window = self.alm_done = False
            self.alm_last = ""
            return
        sh, sm = (int(x) for x in self.s("watersupply_alm_start_time").split(":"))
        total = sh * 60 + sm + int(self.f("watersupply_alm_duration"))
        end = f"{(total // 60) % 24:02d}:{total % 60:02d}"
        in_window = in_schedule(now, days, self.s("watersupply_alm_start_time"), end)
        if not in_window:
            if self.alm_in_window and not self.alm_done:
                self.alm_last = "failed"
                self._log("ALM: window over — temperature not reached/held")
            self.alm_in_window = self.alm_active = False
            return
        if not self.alm_in_window:  # window starts
            self.alm_in_window, self.alm_done, self.alm_hold_since = True, False, None
        if self.alm_done:
            self.alm_active = False
            return
        ihb = temps.get(TANK_SENSOR)
        if ihb is not None and ihb >= self.f("watersupply_alm_temp"):
            if self.alm_hold_since is None:
                self.alm_hold_since = self.t
            elif self.t - self.alm_hold_since >= ALM_HOLD_S:
                self.alm_done, self.alm_active, self.alm_last = True, False, "ok"
                self._log("ALM: disinfection complete")
                return
        elif ihb is not None:
            self.alm_hold_since = None   # dropped below: the hold starts over
        if not self.alm_active:
            self._log("ALM: anti-legionella heating started")
        self.alm_active = True

    def _update_boiler(self, temps: dict[str, float]) -> None:
        # the relay as the last cycle left it (interlocks included): when did it last switch?
        if self.relays["boiler"] != self.boiler_last:
            self.boiler_last, self.boiler_changed_at = self.relays["boiler"], self.t
        bt = temps.get("tsboiler_s")
        max_temp = self.f("heating_boiler_max_temp")
        if bt is not None and bt >= max_temp:
            self.relays["boiler"] = False
            return
        if not self.b("heating_boiler_automode"):
            self.relays["boiler"] = self.b("heating_boiler_power")
            return
        if bt is None:
            # brief dropout: keep the relay. Sustained loss in frost: let the boiler run on its own
            # thermostat (cold is the bigger danger); in mild weather the interlock switches it off
            if self.boiler_sensor_lost and not self._mild_outside():
                self.relays["boiler"] = True
            return
        target = 0.0
        if self.b("heating_radiator_pump"):
            target = max(target, self.radiator_target())
        if self.b("heating_floorheating_pump"):
            target = max(target, self.floor_target())
        # the tank only while it loads, and hot enough for the coil to reach its target
        if (self.b("watersupply_ihb_automode") or self.b("watersupply_ihb_pump")) and (
                self.ihb_heating or self.relays["ihb_pump"]):
            target = max(target, self.ihb_target() + self.f("watersupply_ihb_boost"))
        if target > 0:
            target = max(target, self.f("heating_boiler_min_temp"))   # non-condensing: no flue condensation
        else:
            target = self.f("heating_boiler_temp")
        target = min(target, max_temp - BOILER_TARGET_MARGIN - BOILER_HYSTERESIS)
        self.boiler_auto_target = target
        if self.frost_protect and not self.pressure_zero:
            return  # the interlock holds it on (firmware: no AUTO OFF/ON churn)
        on = self.relays["boiler"]
        held = self.t - self.boiler_changed_at if self.boiler_changed_at is not None else None
        if not on and bt < target and (held is None or held >= BOILER_MIN_OFF_S):
            self.relays["boiler"] = True
        elif on and bt >= target + BOILER_HYSTERESIS and (held is None or held >= BOILER_MIN_ON_S):
            self.relays["boiler"] = False

    def _update_pumps(self, temps: dict[str, float]) -> None:
        if self.b("watersupply_ihb_automode"):
            ihb = temps.get(TANK_SENSOR)
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

    def _update_autofill(self, pressure: float | None) -> None:
        if self.autofill_closing or pressure is None:
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
        elif PRESSURE_ZERO_BAR <= pressure < p_min:  # at ~0 it's a broken sensor or an empty system
            self.relays["af_close"] = False
            self.relays["af_open"] = True
            self.autofill_active = True
            self.autofill_start = self.t
            self._log(f"AUTOFILL: low pressure ({pressure:.2f} bar) — opening valve")

    def _update_teh(self, temps: dict[str, float]) -> None:
        ihb = temps.get(TANK_SENSOR)
        if ihb is None or ihb >= self.ihb_target():  # no tank sensor: never heat blind, in any mode
            self.relays["teh"] = False
            self.teh_delay_active = False
            return
        if not self.b("watersupply_ihb_teh_automode"):
            self.relays["teh"] = self.b("watersupply_ihb_teh_power")
            return
        bt = temps.get("tsboiler_s")
        boiler_heats_tank = (self.relays["boiler"] and self.relays["ihb_pump"]
                             and bt is not None and bt > ihb + TEH_BOILER_MARGIN)
        if boiler_heats_tank:
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

    def _drive_valve(self, vs: ValveState, open_r: str, close_r: str, target: float, actual: float | None,
                     pump_on: bool) -> None:
        self._finish_pulse(vs, open_r, close_r)
        # No flow, no regulation: the standing circuit cools down and the valve would wind fully open,
        # sending boiler water into the circuit when its pump restarts (DHW priority, manual stop).
        # Hold the position, and after a start wait until the sensor sees mixed water.
        if not pump_on:
            vs.pump_since = None
            return
        if vs.pump_since is None:
            vs.pump_since = self.t
        if self.t - vs.pump_since < VALVE_SETTLE_S:
            return
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
        # the pumps as they will run this cycle: frost protection forces them on later, in the interlocks
        frost = self.frost_protect and not self.pressure_zero
        self._drive_valve(self.rad_valve, "rad_open", "rad_close", self.radiator_target(), temps.get("tsrad_s"),
                          self.relays["rad_pump"] or frost)
        self._drive_valve(self.floor_valve, "floor_open", "floor_close", self.floor_target(), temps.get("tsfloor_s"),
                          (self.relays["floor_pump"] or frost) and not self.floor_sensor_lost)

    def _apply_interlocks(self, temps: dict[str, float]) -> None:
        bt = temps.get("tsboiler_s")
        self.overtemp = bt is not None and bt >= self.f("heating_boiler_max_temp")
        reason = None
        if self.overtemp:
            reason = "OVERTEMP"
        elif not self.frost_protect and not self.b("heating_boiler_automode") and not self.b("heating_boiler_power"):
            reason = "MANUAL OFF"
        elif self.frost_protect:
            reason = None  # frost protection beats manual OFF and the sensor-lost switch-off
        elif self.b("heating_boiler_automode") and self.boiler_sensor_lost and self._mild_outside():
            reason = "SENSOR LOST"
        if reason and self.relays["boiler"]:
            self.relays["boiler"] = False
            self._log(f"BOILER: INTERLOCK OFF ({reason})")
        if self.autofill_fault and self.relays["af_open"]:
            self._close_autofill()
        # frost protection — but never run the pumps dry in an emptied system
        if self.frost_protect and not self.pressure_zero:
            self.relays["rad_pump"] = self.relays["floor_pump"] = True
            if not self.overtemp:
                self.relays["boiler"] = True
        # no mechanical limit thermostat on the floor: without its supply sensor the valve is blind
        if self.floor_sensor_lost:
            self.relays["floor_pump"] = False

    def _update_alarms(self, temps: dict[str, float], pressure: float | None) -> None:
        """Lamps. Critical = a set of named causes, so a buzzer mute covers exactly the causes seen then."""
        bt = temps.get("tsboiler_s")
        p_min, p_max = self.f("heating_pressure_min"), self.f("heating_pressure_max")
        max_temp = self.f("heating_boiler_max_temp")
        warning = False
        causes: set[str] = set()
        if pressure is not None and pressure < PRESSURE_ZERO_BAR:
            causes.add("pressure_zero")
        elif pressure is not None:
            if pressure < p_min or pressure > p_max:
                warning = True
            hyst = PRESSURE_CRIT_HYSTERESIS if "pressure" in self.critical_causes else 0.0
            if pressure < p_min - 0.3 + hyst or pressure > p_max + 0.3 - hyst:
                causes.add("pressure")
        if bt is not None:
            warning |= bt >= max_temp - 2   # the auto cycle tops out at max - 5; this is the real approach
            if bt >= max_temp:
                causes.add("boiler_max")
        else:
            warning = True
        if (self.b("heating_radiator_pump") and temps.get("tsrad_s") is None) or (
            self.b("heating_floorheating_pump") and temps.get("tsfloor_s") is None
        ):
            warning = True
        if self.b("watersupply_ihb_automode") and self.ihb_sensor_lost:
            causes.add("ihb_sensor")
        for name in ("boiler_sensor_lost", "overtemp", "autofill_fault", "frost_protect"):
            if getattr(self, name):
                causes.add(name)
        if self.boiler_no_heat:
            if self.outdoor_fresh() and self.outdoor < 0:
                causes.add("boiler_no_heat")
            else:
                warning = True
        if self.well_dry or self.ihb_sensor_lost or self.floor_sensor_lost:
            warning = True
        critical = bool(causes)
        for cause in causes:
            self.cause_seen_at[cause] = self.t
        # a muted cause gone for MUTE_FORGET_S is forgotten (its return is news); a flapping one stays muted
        self.muted_causes = {m for m in self.muted_causes if self.t - self.cause_seen_at.get(m, -1e9) < MUTE_FORGET_S}
        self.critical_causes = causes
        self.warning, self.critical = warning, critical
        self.relays["lamp_warning"] = warning
        self.relays["lamp_critical"] = bool(causes - self.muted_causes)

    def buzzer_mute(self) -> None:
        """Silence the alarm lamp + buzzer for the causes active now; a new cause sounds again."""
        self.muted_causes = set(self.critical_causes)
        self.relays["lamp_critical"] = False
        self._log("ALARM: buzzer muted")

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
            hb["outdoor_pza"] = round(self.outdoor_smooth, 1)
        if self.indoor is not None and self.t - self.indoor_at < INDOOR_TTL_S:
            hb["indoor"] = round(self.indoor, 1)
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
            "pressure_zero": self.pressure_zero,
            "frost_protect": self.frost_protect,
            "boiler_no_heat": self.boiler_no_heat,
            "ihb_sensor_lost": self.ihb_sensor_lost,
            "well_dry": self.well_dry,
            "floor_sensor_lost": self.floor_sensor_lost,
            "alm_no_time": False,             # the emulator always knows the time
            "reset_reason": self.reset_reason,
            "buzzer_muted": self.critical and not self.relays["lamp_critical"],
        })
        if self.alm_last:
            hb["alm_last"] = self.alm_last
        return hb
