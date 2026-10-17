"""Efficiency advice from the circuits' supply − return differences (not alarms: no banner, no buzzer).

Every HealthMonitor poll adds a sample (scheme state: readings, relays, night-schedule flags). A rule averages
the last 30 min of its circuit, using only steady samples: the circuit pump has run ≥ 10 min and its night
setback hasn't switched for 15 min (after a start or a mode change the difference says nothing). Advice goes
through an AlarmTracker with its own raise delays; while a rule can't judge (pump off, not steady yet) its
advice is held, not cleared.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.services.alarm_rules import Alarm, Snapshot

WINDOW = timedelta(minutes=30)
STEADY_AFTER = timedelta(minutes=10)      # pump running this long: the difference reflects the flow
SCHEDULE_SETTLE = timedelta(minutes=15)   # after a night setback switch
MIN_SPAN = timedelta(minutes=20)          # steady samples must cover this much of the window
MIN_SAMPLES = 10
HYSTERESIS = 1.0                          # an active advice clears only this far inside the norm

CIRCUIT_DELAY_S = 60 * 60
RETURN_DELAY_S = 30 * 60

# (code, label, supply role, return role, pump relay, schedule flag, low, high, low text, high text);
# the norms are the scheme's colours too (frontend/src/scheme/deltas.ts) — change both together
CIRCUITS = [
    # Beretta City 28 CSI: rated 80/60 — the boiler's difference stays within 20°
    ("boiler", "Котёл", "boiler_supply", "boiler_return", "boiler", None, 8.0, 20.0,
     "насос котла гонит больше, чем забирают контуры: горячая вода через гидрострелку сразу уходит в обратку — "
     "снизьте скорость насоса котла, но не ниже паспортного минимального расхода котла",
     "через котёл мало расхода (паспортный режим 80/60, разница до 20°) — проверьте скорость насоса котла, "
     "фильтр на обратке и кран на перемычке гидрострелки: он должен быть полностью открыт"),
    ("rad", "Радиаторы", "rad_supply", "rad_return", "rad_pump", "schedule_rad", 5.0, 25.0,
     "насос радиаторов гонит лишнее (или радиатор работает перемычкой) — снизьте скорость насоса радиаторов",
     "радиаторам не хватает расхода: воздух, забитый фильтр или слабый насос. В тёплую погоду, когда "
     "термоголовки прикрыты, это нормально"),
    ("floor", "Тёплый пол", "floor_supply", "floor_return", "floor_pump", "schedule_floor", 3.0, 10.0,
     "насос тёплого пола гонит лишнее — его можно сбавить и сэкономить электричество",
     "петлям не хватает расхода, пол греется неравномерно — проверьте воздух в петлях, расходомеры на гребёнке "
     "и скорость насоса"),
]
BOILER_RETURN_MIN = 50.0                  # non-condensing boiler: flue gas condenses below this
COIL_START = (timedelta(minutes=3), timedelta(minutes=15))   # the start of a tank loading
COIL_MIN_DELTA = 5.0
COIL_COLD_TANK = 5.0                      # the tank this far below its target: the coil should give a lot

# Expansion vessel: the heating pressure between a cold and a hot system over the last day
LONG_WINDOW = timedelta(hours=24)
LONG_STEP = timedelta(minutes=5)          # one long-history point per 5 min
LONG_MIN_SPAN = timedelta(hours=12)
PRESSURE_SWING = 0.5                      # bar more when hot than when cold: the vessel lost its air
PRESSURE_SWING_CLEAR = 0.4
SWING_MIN_HEAT = 20.0                     # °C between the cold and the hot samples, or there's nothing to compare


@dataclass
class Sample:
    t: datetime
    values: dict[str, float | None]
    relays: dict[str, bool]
    flags: dict[str, bool]
    ihb_target: float | None


@dataclass
class AdviceHistory:
    samples: deque[Sample] = field(default_factory=deque)
    on_since: dict[str, datetime | None] = field(default_factory=dict)        # relay → switched on at
    flag_changed: dict[str, datetime] = field(default_factory=dict)            # schedule flag → last switch
    _last_flags: dict[str, bool] = field(default_factory=dict)
    long: deque[tuple[datetime, float, float]] = field(default_factory=deque)  # (t, heating bar, boiler supply)

    def add(self, s: Snapshot) -> None:
        relays = {k: bool(v) for k, v in s.relays.items()} if s.online else {}
        for relay in {c[4] for c in CIRCUITS} | {"ihb_pump"}:
            on = relays.get(relay, False)
            if not on:
                self.on_since[relay] = None
            elif self.on_since.get(relay) is None:
                self.on_since[relay] = s.now
        for flag in ("schedule_rad", "schedule_floor"):
            v = bool(s.flags.get(flag, False))
            if flag in self._last_flags and self._last_flags[flag] != v:
                self.flag_changed[flag] = s.now
            self._last_flags[flag] = v
        values = {role: (None if r.get("stale") else r.get("value")) for role, r in s.values.items()}
        self.samples.append(Sample(s.now, values, relays, dict(s.flags), s.targets.get("ihb")))
        while self.samples and s.now - self.samples[0].t > WINDOW:
            self.samples.popleft()
        p, t = values.get("heating_pressure"), values.get("boiler_supply")
        if p is not None and t is not None and (not self.long or s.now - self.long[-1][0] >= LONG_STEP):
            self.long.append((s.now, p, t))
            while self.long and s.now - self.long[0][0] > LONG_WINDOW:
                self.long.popleft()

    def pressure_swing(self) -> tuple[float, float, float, float] | None:
        """(cold bar, hot bar, cold °C, hot °C): the coldest and the hottest fifth of the day's points."""
        if len(self.long) < 50 or self.long[-1][0] - self.long[0][0] < LONG_MIN_SPAN:
            return None
        pts = sorted(self.long, key=lambda x: x[2])
        n = max(5, len(pts) // 5)
        cold, hot = pts[:n], pts[-n:]
        mean = lambda xs, i: sum(x[i] for x in xs) / len(xs)  # noqa: E731
        tc, th = mean(cold, 2), mean(hot, 2)
        if th - tc < SWING_MIN_HEAT:
            return None
        return mean(cold, 1), mean(hot, 1), tc, th

    def steady(self, relay: str, flag: str | None, t: datetime) -> bool:
        since = self.on_since.get(relay)
        if since is None or t - since < STEADY_AFTER:
            return False
        changed = self.flag_changed.get(flag) if flag else None
        return changed is None or t - changed >= SCHEDULE_SETTLE

    def average(self, now: datetime, relay: str, flag: str | None, f) -> float | None:
        """Mean of f(sample) over the window's steady samples; None if they don't cover enough of it."""
        if not self.steady(relay, flag, now):
            return None
        since = self.on_since[relay]
        pts = [(x.t, f(x)) for x in self.samples
               if x.t - since >= STEADY_AFTER and x.relays.get(relay)
               and (not flag or flag not in self.flag_changed or x.t - self.flag_changed[flag] >= SCHEDULE_SETTLE)]
        pts = [(t, v) for t, v in pts if v is not None]
        if len(pts) < MIN_SAMPLES or pts[-1][0] - pts[0][0] < MIN_SPAN:
            return None
        return sum(v for _, v in pts) / len(pts)


def _delta(sup: str, ret: str):
    def f(x: Sample) -> float | None:
        a, b = x.values.get(sup), x.values.get(ret)
        return None if a is None or b is None else a - b
    return f


def _f(v: float) -> str:
    return f"{v:.1f}"


def evaluate_advice(h: AdviceHistory, now: datetime, active: set[str]) -> tuple[list[Alarm], set[str]]:
    """Advice that holds now, and the codes that can't be judged right now (their advice is held)."""
    out: list[Alarm] = []
    held: set[str] = set()

    for code, label, sup, ret, relay, flag, low, high, low_text, high_text in CIRCUITS:
        d = h.average(now, relay, flag, _delta(sup, ret))
        lo, hi = f"delta_low:{code}", f"delta_high:{code}"
        if d is None:
            held |= {lo, hi}
            continue
        if d < low or (lo in active and d < low + HYSTERESIS):
            out.append(Alarm(lo, "INFO", f"{label}: разница подачи и обратки {_f(d)}° (норма от {low:g}°) — {low_text}",
                             CIRCUIT_DELAY_S))
        if d > high or (hi in active and d > high - HYSTERESIS):
            out.append(Alarm(hi, "INFO", f"{label}: разница подачи и обратки {_f(d)}° (норма до {high:g}°) — {high_text}",
                             CIRCUIT_DELAY_S))

    # non-condensing boiler: a cold return condenses flue gas in its heat exchanger
    ret = h.average(now, "boiler", None, lambda x: x.values.get("boiler_return"))
    code = "boiler_return_low"
    if ret is None:
        held.add(code)
    elif ret < BOILER_RETURN_MIN or (code in active and ret < BOILER_RETURN_MIN + 2):
        out.append(Alarm(code, "INFO",
                         f"Обратка котла {_f(ret)}° — ниже {BOILER_RETURN_MIN:g}° обычный котёл конденсирует дымовые газы "
                         f"и ржавеет. Поднимите мин. температуру котла или снизьте расход насоса котла; надёжно — "
                         f"термосмесительный клапан защиты обратки на 55°", RETURN_DELAY_S))

    # the tank coil at the start of a loading: a cold tank must take a lot of heat
    since = h.on_since.get("ihb_pump")
    code = "coil_poor"
    start = [x for x in h.samples
             if since is not None and COIL_START[0] <= x.t - since <= COIL_START[1] and x.relays.get("ihb_pump")
             and x.ihb_target is not None and x.values.get("tank") is not None
             and x.values["tank"] < x.ihb_target - COIL_COLD_TANK]
    deltas = [d for d in (_delta("coil_supply", "coil_return")(x) for x in start) if d is not None]
    if since is None or now - since < COIL_START[1] or len(deltas) < 3:
        held.add(code)
    else:
        d = sum(deltas) / len(deltas)
        if d < COIL_MIN_DELTA or (code in active and d < COIL_MIN_DELTA + HYSTERESIS):
            out.append(Alarm(code, "INFO",
                             f"Змеевик бойлера: в начале загрузки разница подачи и обратки змеевика всего {_f(d)}° при "
                             f"холодном баке — змеевик плохо отдаёт тепло (накипь или воздух). Стоит промыть змеевик"))
    # expansion vessel: the system pressure rises with temperature much more than a healthy vessel allows
    code = "expansion_vessel"
    swing = h.pressure_swing()
    if swing is None:
        held.add(code)
    else:
        pc, ph, tc, th = swing
        if ph - pc > PRESSURE_SWING or (code in active and ph - pc > PRESSURE_SWING_CLEAR):
            out.append(Alarm(code, "INFO",
                             f"Давление в отоплении растёт с нагревом на {ph - pc:.2f} бар ({pc:.2f} бар при {tc:.0f}° → "
                             f"{ph:.2f} бар при {th:.0f}°) — похоже, в расширительном баке мало воздуха: проверьте его "
                             f"давление (на 0,2–0,3 бар ниже давления холодной системы) и мембрану. Отсюда и частая подпитка"))
    return out, held
