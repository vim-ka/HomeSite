"""What is wrong in the house right now — alarm rules and the tracker of active alarms.

`evaluate()` is pure: it looks at one snapshot (the scheme state plus rooms, services and the raw
controller heartbeat) and lists the conditions that are true now. `AlarmTracker` turns that into
active alarms: a condition must hold for its delay before it is raised, and an alarm clears as soon
as its condition is gone (hysteresis lives in the rules, which see the active codes).

The HealthMonitor runs both every poll and logs raise/clear events; the scheme page and the header
read the active list, so the event log and the screen never disagree.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from app.services.controller_flags import CONTROLLER_FLAGS

LEVEL_RANK = {"INFO": 0, "WARNING": 1, "ERROR": 2}

ROOM_DELAY_S = 10 * 60
ROOM_THRESHOLDS = [  # (below, level, text) — checked coldest first
    (5.0, "ERROR", "Угроза замерзания в помещении «{name}»: {v} °C"),
    (10.0, "ERROR", "Холодно в помещении «{name}»: {v} °C — проверьте отопление"),
    (15.0, "WARNING", "Прохладно в помещении «{name}»: {v} °C"),
]
BOILER_ROOM_THRESHOLDS = [
    (3.0, "ERROR", "ОПАСНОСТЬ РАЗМОРОЗКИ: в котельной {v} °C"),
    (5.0, "ERROR", "Холодно в котельной: {v} °C — трубы могут замёрзнуть"),
    (8.0, "WARNING", "Прохладно в котельной: {v} °C"),
]
TEMP_HYSTERESIS = 1.0

PRESSURE_EMERGENCY_FLOOR = 0.8   # the emergency level is min - 0.2, but never below this
PRESSURE_RELIEF_WARN = 2.5       # safety valve opens at ~3 bar
PRESSURE_HYSTERESIS = 0.05


@dataclass(frozen=True)
class Alarm:
    code: str
    level: str
    text: str
    delay_s: int = 0


@dataclass
class Snapshot:
    now: datetime
    services: dict[str, bool]                 # gateway, mqtt
    online: bool                              # controller heartbeat is fresh
    values: dict[str, dict]                   # role → {"value", "stale"} (scheme state)
    relays: dict[str, bool]
    flags: dict[str, bool]
    targets: dict[str, float | None]
    settings: dict[str, str]
    rooms: list[tuple[str, float | None]]     # heated rooms: (name, fresh value or None)
    hb: dict = field(default_factory=dict)    # raw controller heartbeat data ({} when offline)


def _fmt(v: float) -> str:
    return f"{v:.1f}".replace("-", "−")


def _num(settings: dict[str, str], key: str, default: float) -> float:
    try:
        return float(settings[key])
    except (KeyError, ValueError):
        return default


def _val(s: Snapshot, role: str) -> float | None:
    r = s.values.get(role) or {}
    return None if r.get("stale") or r.get("value") is None else float(r["value"])


def _cold(code: str, v: float | None, thresholds, active: set[str], **fmt) -> Alarm | None:
    if v is None:
        return None
    extra = TEMP_HYSTERESIS if code in active else 0.0
    for below, level, text in thresholds:
        if v < below + extra:
            return Alarm(code, level, text.format(v=_fmt(v), **fmt), ROOM_DELAY_S)
    return None


def evaluate(s: Snapshot, active: set[str]) -> list[Alarm]:
    out: list[Alarm | None] = []
    add = out.append

    # --- services and the link to the controller
    if not s.services.get("gateway", True):
        add(Alarm("svc:gateway", "ERROR", "Шлюз устройств недоступен — команды и данные контроллера не проходят", 30))
    elif not s.services.get("mqtt", True):
        add(Alarm("svc:mqtt", "ERROR", "Брокер MQTT недоступен — нет связи с контроллером и датчиками", 60))
    elif not s.online:
        outdoor = _val(s, "outdoor")
        text = "Нет связи с контроллером котельной"
        if outdoor is not None and outdoor < 0:
            text += (f" (на улице {outdoor:.0f} °C)".replace("-", "−")
                     + ". Если контроллер не работает, котёл и насосы выключены — проверьте котельную")
        add(Alarm("no_link", "ERROR", text, 60))

    # --- controller safety flags (held by the tracker while the controller is unreachable)
    if s.online:
        for flag, (level, text) in CONTROLLER_FLAGS.items():
            if s.flags.get(flag):
                add(Alarm(f"flag:{flag}", level, text))
        if (s.hb.get("rad_wbm") or s.hb.get("floor_wbm")) and "outdoor" not in s.hb:
            add(Alarm("pza_no_outdoor", "WARNING",
                      "Нет уличной температуры — погодное регулирование (ПЗА) не работает, действуют ручные уставки",
                      5 * 60))
        if s.hb.get("alm_last") == "failed":
            add(Alarm("alm_failed", "WARNING",
                      f"Термодезинфекция не выполнена: бойлер не нагрелся до "
                      f"{_num(s.settings, 'watersupply_alm_temp', 60):.0f} °C"))
        if s.hb.get("alm_no_time"):
            add(Alarm("alm_no_time", "WARNING",
                      "Контроллер не знает точного времени — термодезинфекция и ночные режимы не работают"))

    # --- rooms, boiler room, water pipes
    for name, v in s.rooms:
        add(_cold(f"room:{name}", v, ROOM_THRESHOLDS, active, name=name))
    add(_cold("boiler_room", _val(s, "boiler_room"), BOILER_ROOM_THRESHOLDS, active))
    cold = _val(s, "cold_water")
    if cold is not None and cold < 3.0 + (TEMP_HYSTERESIS if "cold_water" in active else 0):
        add(Alarm("cold_water", "ERROR", f"Холодная вода {_fmt(cold)} °C — трубы водопровода могут замёрзнуть",
                  ROOM_DELAY_S))

    # --- heating pressure (0 bar is the controller's pressure_zero flag)
    p = _val(s, "heating_pressure")
    if p is not None and not s.flags.get("pressure_zero") and p >= 0.05:
        p_min = _num(s.settings, "heating_pressure_min", 1.0)
        p_max = _num(s.settings, "heating_pressure_max", 1.8)
        emergency = max(PRESSURE_EMERGENCY_FLOOR, p_min - 0.2)

        def below(code: str, limit: float) -> bool:
            return p < limit + (PRESSURE_HYSTERESIS if code in active else 0)

        def above(code: str, limit: float) -> bool:
            return p > limit - (PRESSURE_HYSTERESIS if code in active else 0)

        if below("pressure_low", emergency):
            add(Alarm("pressure_low", "ERROR", f"Давление в отоплении {p:.2f} бар — ниже аварийного {emergency:g} бар", 60))
        elif below("pressure_low_long", p_min):
            why = ("подпитка не справляется (утечка?)" if s.settings.get("heating_autofill_enabled") == "1"
                   else "автоподпитка выключена — долейте систему")
            add(Alarm("pressure_low_long", "WARNING", f"Давление {p:.2f} бар ниже нормы {p_min:g} уже 10 мин — {why}",
                      10 * 60))
        if above("pressure_high", PRESSURE_RELIEF_WARN):
            add(Alarm("pressure_high", "ERROR",
                      f"Давление в отоплении {p:.2f} бар — близко к срабатыванию предохранительного клапана", 60))
        elif above("pressure_high_long", p_max):
            add(Alarm("pressure_high_long", "WARNING",
                      f"Давление {p:.2f} бар выше нормы {p_max:g} уже 10 мин — проверьте расширительный бак", 10 * 60))

    # --- circuits that don't warm up although the boiler is hot (pump or 3-way valve failure)
    boiler = _val(s, "boiler_supply")
    for circuit, relay, title in (("rad", "rad_pump", "Радиаторы"), ("floor", "floor_pump", "Тёплый пол")):
        supply, target = _val(s, f"{circuit}_supply"), s.targets.get(circuit)
        if (s.online and s.relays.get(relay) and supply is not None and target is not None and boiler is not None
                and supply < target - 8 and boiler > supply + 15):
            add(Alarm(f"no_heat:{circuit}", "ERROR",
                      f"{title} не прогреваются: подача {_fmt(supply)} °C при цели {target:.0f} °C, котёл {_fmt(boiler)} °C. "
                      "Проверьте насос и трёхходовой клапан", 20 * 60))

    # --- DHW tank
    tank, tank_target = _val(s, "tank"), s.targets.get("ihb")
    if tank is not None and tank >= max(80.0, (tank_target or 0) + 10):
        add(Alarm("tank_overheat", "ERROR",
                  f"Бойлер ГВС перегрет ({_fmt(tank)} °C) — ТЭН или насос загрузки не отключается, опасность ожога", 120))
    if (s.online and s.relays.get("ihb_pump") and tank is not None and tank_target is not None and boiler is not None
            and tank < tank_target - 5 and boiler > tank + 10):
        add(Alarm("tank_no_heat", "WARNING",
                  f"Бойлер ГВС не нагревается: {_fmt(tank)} °C при цели {tank_target:.0f} °C, котёл {_fmt(boiler)} °C — "
                  "проверьте насос загрузки", 60 * 60))

    # --- sensor sanity
    ret = _val(s, "boiler_return")
    if (s.online and any(s.relays.get(r) for r in ("rad_pump", "floor_pump", "ihb_pump"))
            and boiler is not None and ret is not None and boiler < ret - 3):
        add(Alarm("supply_below_return", "WARNING",
                  "Подача котла холоднее обратки — перепутаны датчики или вода идёт в обратную сторону", 10 * 60))

    return [a for a in out if a is not None]


class AlarmTracker:
    """Active alarms with raise delays. `update()` returns what was raised and what cleared this time."""

    def __init__(self) -> None:
        self.active: dict[str, Alarm] = {}
        self._pending: dict[str, datetime] = {}
        self._since: dict[str, datetime] = {}
        self._acked: set[str] = set()   # acknowledged by a person; reset when the alarm gets worse or clears

    def update(self, alarms: Iterable[Alarm], now: datetime,
               hold_prefixes: tuple[str, ...] = ()) -> tuple[list[Alarm], list[Alarm]]:
        seen = {a.code: a for a in alarms}
        raised: list[Alarm] = []
        for code, a in seen.items():
            if code in self.active:
                old = self.active[code]
                if LEVEL_RANK[a.level] > LEVEL_RANK[old.level]:
                    raised.append(a)          # escalation is news
                    self._acked.discard(code)
                self.active[code] = a         # keep the text current (values change)
                continue
            since = self._pending.setdefault(code, now)
            if (now - since).total_seconds() >= a.delay_s:
                self._pending.pop(code)
                self.active[code] = a
                self._since[code] = now
                raised.append(a)
        for code in [c for c in self._pending if c not in seen]:
            self._pending.pop(code)
        cleared = [self.active.pop(code) for code in list(self.active)
                   if code not in seen and not code.startswith(hold_prefixes or ("\0",))]
        for a in cleared:
            self._since.pop(a.code, None)
            self._acked.discard(a.code)
        return raised, cleared

    def ack(self, code: str) -> bool:
        if code not in self.active:
            return False
        self._acked.add(code)
        return True

    def active_list(self) -> list[dict]:
        items = sorted(self.active.values(), key=lambda a: (-LEVEL_RANK[a.level], a.code))
        return [{"code": a.code, "level": a.level, "text": a.text,
                 "since": self._since[a.code].isoformat() if a.code in self._since else None,
                 "acked": a.code in self._acked} for a in items]
