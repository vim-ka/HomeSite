"""Boiler room piping drawings from one topology.

Usage: python3 docs/boiler-room/draw_piping.py   → writes 02-piping.svg (A, GOST style) and 01-overview.svg (B, colour)

The boiler stands on the right as in the real room (and on the site's scheme). Every item carries data-pos
(specification position) and, for electrical parts, data-ref (ГОСТ 2.710 code) — check_docs.py cross-checks them
with 03-specification.md. Rev. 2 follows the plumber review (kotelna.tk practice).
"""

from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
W, H = 1400, 900            # wiring sheets
PW, PH = 1600, 1150         # piping sheets
FONT = "Arial, Helvetica, sans-serif"

# Fittings left out of the colour overview; filters, reducer, safety units and the DHW mixer stay on it
SMALL = {"22", "24", "25", "26", "27", "28", "29", "30", "32", "34", "37", "38", "39", "40", "41", "42", "43", "44",
         "45", "46", "47", "48"}

# Separator: boiler supply enters above the collector outlet (air to the vent), boiler return leaves below the
# collector return (sludge settles to the drain) — kotelna.tk 1-1-8-44
SEPARATOR = {"x": 1000, "top": 420, "bottom": 640, "boiler_supply_y": 445, "collector_supply_y": 482,
             "collector_return_y": 572, "boiler_return_y": 615}

# x of the fittings on the boiler pipes (boiler on the right: larger x = boiler side). The safety group, the filter and
# the expansion tank stay connected to the boiler when its shut-off valves are closed.
BOILER_SIDE = {"supply_valve": 1075, "safety_group": 1205, "return_valve": 1075, "filter": 1115, "bp1": 1195,
               "tank_tee": 1235}

# Make-up in flow order (positions): shut-off, strainer, reducer 1.5 bar, check / disconnector, flow limiter, YA3;
# a bypass with its own valve goes round the last two (kotelna.tk 1-1-6-1, «Автоматизация подпитки»)
MAKE_UP_ORDER = ["29", "29", "36", "29", "37", "13"]

COLOURS = {"Т1": "#ef4444", "Т2": "#3b82f6", "Т3": "#ec4899", "Т4": "#f97316", "В1": "#0ea5e9", "Г1": "#ca8a04"}


class Sheet:
    def __init__(self, style: str):
        self.style = style
        self.gost = style == "gost"
        self.fg = "#000" if self.gost else "#334155"
        self.bg = "#fff"
        self.out: list[str] = []

    # --- primitives ---------------------------------------------------------------------------
    def add(self, s: str) -> None:
        self.out.append(s)

    def text(self, x, y, s, size=11, anchor="middle", weight="normal", fill=None) -> str:
        return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
                f'fill="{fill or self.fg}" stroke="none">{escape(s)}</text>')

    def pipe(self, code: str, pts, codes=()) -> None:
        """A pipeline in flow order; `codes` — points where its code (Т1…) is written over the line."""
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        colour = self.fg if self.gost else COLOURS[code]
        width = 1.8 if self.gost else 4
        dash = ' stroke-dasharray="10 3 2 3"' if code == "Г1" and self.gost else ""
        self.add(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width}"{dash} stroke-linejoin="round"/>')
        for x, y in codes:
            self.add(f'<rect x="{x - 11}" y="{y - 7}" width="22" height="14" fill="{self.bg}"/>'
                     + self.text(x, y + 4, code, 10, weight="bold", fill=colour))

    def item(self, pos, ref, body: str, leader=None, title="") -> None:
        """An item group; leader = (x, y, dx, dy): line from (x, y) to a shelf with the position number."""
        if not self.gost and str(pos) in SMALL:
            return
        attrs = f' data-pos="{pos}"' if pos else ""
        attrs += f' data-ref="{ref}"' if ref else ""
        lead = ""
        if leader and pos:
            x, y, dx, dy = leader
            ex, ey = x + dx, y + dy
            sx = ex + (20 if dx >= 0 else -20)
            lead = (f'<path d="M{x},{y} L{ex},{ey} L{sx},{ey}" fill="none" stroke="{self.fg}" stroke-width="0.7"/>'
                    + self.text((ex + sx) / 2, ey - 3, str(pos), 11, weight="bold"))
        tip = f"<title>{escape(title)}</title>" if title else ""
        self.add(f"<g{attrs}>{tip}{body}{lead}</g>")

    def g(self, x, y, rot, inner: str) -> str:
        return f'<g transform="translate({x} {y}) rotate({rot})" stroke="{self.fg}" stroke-width="1.3">{inner}</g>'

    # --- symbols (ГОСТ 21.205, simplified), local axis: flow along +x ----------------------------
    def valve(self, x, y, rot=0) -> str:
        return self.g(x, y, rot, f'<path d="M-8,-5 L8,5 V-5 L-8,5 Z" fill="{self.bg}"/><circle r="2.2" fill="{self.fg}"/>')

    def check(self, x, y, rot=0) -> str:
        return self.g(x, y, rot, f'<path d="M-8,-5 L8,5 V-5 L-8,5 Z" fill="{self.bg}"/><path d="M0,0 L8,5 V-5 Z" fill="{self.fg}"/>')

    def strainer(self, x, y, rot=0) -> str:
        return self.g(x, y, rot, f'<path d="M-9,0 L0,-7 L9,0 L0,7 Z" fill="{self.bg}"/><path d="M-4,-4 L4,4 M0,-7 V7" stroke-dasharray="2 2"/>')

    def pump(self, x, y, rot=0) -> str:
        fill = self.bg if self.gost else "#22c55e"
        return self.g(x, y, rot, f'<circle r="11" fill="{fill}"/><path d="M-6,-9.3 L11,0 L-6,9.3" fill="none"/>')

    def actuator(self, x, y, letter="M") -> str:
        return (f'<rect x="{x - 7}" y="{y - 7}" width="14" height="14" fill="{self.bg}" stroke="{self.fg}" stroke-width="1.3"/>'
                + self.text(x, y + 4, letter, 10, weight="bold"))

    def valve3(self, x, y, bypass: str) -> str:
        """3-way mixing valve on a vertical riser: in from below, out upwards (or reversed), bypass from the side."""
        b = -1 if bypass == "left" else 1
        tri = (f'<path d="M-5,9 L5,9 L0,0 Z M-5,-9 L5,-9 L0,0 Z M{9 * b},-5 L{9 * b},5 L0,0 Z" fill="{self.bg}"/>')
        ax = x - 22 * b
        return (self.g(x, y, 0, tri) + f'<path d="M{x},{y} L{ax},{y}" stroke="{self.fg}" stroke-width="1"/>'
                + self.actuator(ax, y))

    def motor_valve(self, x, y, rot=0, side=1, letter="M") -> str:
        ax = x + 22 * side
        return (self.valve(x, y, rot) + f'<path d="M{x},{y} L{ax},{y}" stroke="{self.fg}" stroke-width="1"/>'
                + self.actuator(ax, y, letter))

    def relief(self, x, y) -> str:
        """Safety valve on an upward stem at (x, y): inlet from below, outlet to the right, spring above."""
        return self.g(x, y, 0, f'<path d="M-5,9 L5,9 L0,0 Z" fill="{self.bg}"/><path d="M0,0 L9,-5 V5 Z" fill="{self.bg}"/>'
                               '<path d="M0,0 V-3 L-4,-5 L4,-8 L-4,-11 L4,-14 L0,-16" fill="none"/>'
                               '<path d="M9,0 H16 M13,-3 L16,0 L13,3" fill="none"/>')

    def air_vent(self, x, y) -> str:
        return self.g(x, y, 0, f'<rect x="-5" y="-12" width="10" height="12" fill="{self.bg}"/>'
                               '<path d="M0,-12 V-20 M-3,-17 L0,-20 L3,-17" fill="none"/>')

    def bubble(self, x, y, letters: str) -> str:
        return (f'<circle cx="{x}" cy="{y}" r="11" fill="{self.bg}" stroke="{self.fg}" stroke-width="1.2"/>'
                + self.text(x, y + 3.5, letters, 8, weight="bold"))

    def membrane_tank(self, x, y, w=26, h=44) -> str:
        fill = self.bg if self.gost else "#fecaca"
        return (f'<rect x="{x - w / 2}" y="{y}" width="{w}" height="{h}" rx="{w / 2}" fill="{fill}" stroke="{self.fg}" stroke-width="1.3"/>'
                f'<path d="M{x - w / 2},{y + h / 2} H{x + w / 2}" stroke="{self.fg}" stroke-dasharray="3 2"/>')

    def drain(self, x, y, rot=0) -> str:
        return self.valve(x, y, rot) + self.g(x, y, rot, '<path d="M8,0 H14 M14,0 V8 M11,5 L14,8 L17,5" fill="none"/>')

    def tap(self, x, y) -> str:
        return self.g(x, y, 0, f'<path d="M0,0 V-10 H16 V-4" fill="none" stroke-width="2"/><path d="M-6,-10 H6" stroke-width="3"/>')

    def dielectric(self, x, y) -> str:
        return self.g(x, y, 90, f'<rect x="-5" y="-6" width="10" height="12" fill="{self.bg}"/><path d="M-2,-6 V6 M2,-6 V6"/>')

    def union_valve(self, x, y, rot=0) -> str:
        """Ball valve with a union (кран-американка) — a pump can be taken out between two of them."""
        return self.valve(x, y, rot) + self.g(x, y, rot, '<path d="M11,-6 V6 M14,-6 V6" stroke-width="1.6"/>')

    def reducer(self, x, y, rot=0) -> str:
        """Pressure reducer: valve body with a spring-loaded diaphragm and the outlet arrow."""
        return self.g(x, y, rot, f'<path d="M-8,-5 L8,5 V-5 L-8,5 Z" fill="{self.bg}"/>'
                                 '<path d="M0,0 V-10 M-5,-10 H5 M-3,-13 L3,-16 M-3,-16 L3,-19" fill="none"/>'
                                 '<path d="M3,8 L12,8 M9,5 L12,8 L9,11" fill="none" stroke-width="1"/>')

    def needle(self, x, y, rot=0) -> str:
        """Throttling valve (дроссель): valve with a diagonal arrow."""
        return self.g(x, y, rot, f'<path d="M-8,-5 L8,5 V-5 L-8,5 Z" fill="{self.bg}"/>'
                                 '<path d="M-7,9 L7,-9 M3,-9 H7 V-5" fill="none" stroke-width="1"/>')

    def mixer(self, x, y) -> str:
        """Thermostatic mixer on a vertical line: hot in from below, cold from the left, mixed out upwards."""
        tri = (f'<path d="M-5,9 L5,9 L0,0 Z M-5,-9 L5,-9 L0,0 Z M-9,-5 L-9,5 L0,0 Z" fill="{self.bg}"/>'
               f'<path d="M0,0 H14" stroke-width="1"/><rect x="14" y="-7" width="14" height="14" rx="7" fill="{self.bg}"/>')
        return self.g(x, y, 0, tri) + self.text(x + 21, y + 4, "Т", 9, weight="bold")

    def funnel(self, x, y) -> str:
        """Drain funnel with a visible air gap (сброс клапанов в канализацию)."""
        return self.g(x, y, 0, f'<path d="M-9,0 H9 L3,9 V16 M-3,16 V9 Z" fill="{self.bg}"/>'
                               '<path d="M0,-12 V-5" stroke-dasharray="2 2"/>')

    def gauge(self, pos, x, y, side, letters, dist=24, title="", leader=None) -> None:
        """A local instrument (manometer, dial thermometer) on a stem, no database name."""
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[side]
        bx, by = x + dx * dist, y + dy * dist
        body = (f'<path d="M{x},{y} L{bx - dx * 11},{by - dy * 11}" stroke="{self.fg}" stroke-width="1"/>'
                + self.bubble(bx, by, letters))
        self.item(pos, "", body, leader=leader, title=title)

    # --- instruments ------------------------------------------------------------------------
    def sensor(self, pos, ref, name, x, y, side, letters="TE", dist=28, title=""):
        """Instrument on a pipe at (x, y): stem to a bubble on `side`, then its code and the database name."""
        dx, dy = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}[side]
        bx, by = x + dx * dist, y + dy * dist
        body = f'<path d="M{x},{y} L{bx - dx * 11},{by - dy * 11}" stroke="{self.fg}" stroke-width="1"/>'
        body += self.bubble(bx, by, letters)
        if side == "up":
            body += self.text(bx, by - 26, ref, 10, weight="bold") + self.text(bx, by - 15, name, 9)
        elif side == "down":
            body += self.text(bx, by + 23, ref, 10, weight="bold") + self.text(bx, by + 34, name, 9)
        else:
            anchor = "start" if dx > 0 else "end"
            tx = bx + dx * 15
            body += self.text(tx, by - 2, ref, 10, anchor, "bold") + self.text(tx, by + 10, name, 9, anchor)
        self.item(pos, ref, body, title=title or name)


def draw(s: Sheet) -> None:
    fg, bg = s.fg, s.bg
    eq_fill = bg if s.gost else "#f1f5f9"
    sx, sy0, sy1 = SEPARATOR["x"], SEPARATOR["top"], SEPARATOR["bottom"]
    yS, yR = SEPARATOR["collector_supply_y"], SEPARATOR["collector_return_y"]
    yBS, yBR = SEPARATOR["boiler_supply_y"], SEPARATOR["boiler_return_y"]
    BS, BR, BG = 1270, 1310, 1360            # boiler connections: supply, return, gas
    MU = 1285                                # make-up riser
    CW = 980                                 # treated cold main

    # ===== pipelines (drawn first, equipment over them) =====
    # boiler ↔ separator: supply enters high, return leaves low
    s.pipe("Т1", [(BS, 340), (BS, yBS), (sx + 36, yBS)], codes=[(BS, 400)])
    s.pipe("Т2", [(sx + 36, yBR), (BR, yBR), (BR, 340)], codes=[(BR, 560)])
    # radiators: supply riser x 800 up, return riser x 760 down to the return collector (behind the supply one)
    s.pipe("Т1", [(800, yS - 12), (800, 110)], codes=[(800, 135)])
    s.pipe("Т2", [(760, 110), (760, yR - 12)], codes=[(760, 135)])
    s.pipe("Т2", [(760, 410), (791, 410)])                       # radiator bypass («ножка») into the valve
    # floor: supply riser x 800 down (behind the return collector), return riser x 760 up
    s.pipe("Т1", [(800, yS + 12), (800, 900)], codes=[(800, 893)])
    s.pipe("Т2", [(760, 900), (760, yR + 12)], codes=[(760, 893)])
    s.pipe("Т2", [(760, 640), (791, 640)])                       # floor bypass
    # tank loading: collector → pump → coil → back
    s.pipe("Т1", [(480, yS), (260, yS)], codes=[(300, yS)])
    s.pipe("Т2", [(260, yR), (480, yR)], codes=[(300, yR)])
    # DHW: tank → thermostatic mixer → tap; recirculation back into the tank's middle third
    s.pipe("Т3", [(170, 360), (170, 289)], codes=[(170, 335)])
    s.pipe("Т3", [(170, 271), (170, 140)], codes=[(170, 160)])
    s.pipe("Т4", [(170, 200), (95, 200), (95, 600), (140, 600)], codes=[(95, 520)])
    # cold water: well → pressure tank → treatment → treated main → cold tap / mixer / tank / make-up
    s.pipe("В1", [(65, 1062), (65, 1030), (570, 1030), (570, CW)], codes=[(80, 1046)])
    s.pipe("В1", [(30, CW), (MU, CW)], codes=[(640, CW)])
    s.pipe("В1", [(30, CW), (30, 140)], codes=[(30, 700)])
    s.pipe("В1", [(30, 280), (161, 280)])                       # cold to the mixer
    s.pipe("В1", [(230, CW), (230, 760)])                       # cold to the tank
    s.pipe("В1", [(230, 860), (300, 860), (300, 872)])          # to the DHW expansion tank
    s.pipe("В1", [(MU, CW), (MU, yBR)], codes=[(MU, 690)])      # make-up into the boiler return
    s.pipe("В1", [(MU, 850), (1330, 850), (1330, 700), (MU, 700)])   # bypass around limiter + YA3
    # gas
    s.pipe("Г1", [(1540, 1000), (1540, 370), (BG, 370), (BG, 340)], codes=[(1540, 640)])

    # ===== equipment =====
    # 1 boiler + chimney
    body = (f'<rect x="1240" y="130" width="140" height="210" rx="6" fill="{eq_fill}" stroke="{fg}" stroke-width="1.8"/>'
            + s.text(1310, 225, "Котёл газовый", 12, weight="bold") + s.text(1310, 241, "настенный, 28 кВт", 10)
            + s.text(1310, 255, "открытая камера, OT", 10)
            + f'<path d="M1300,130 V30 M1320,130 V30" stroke="{fg}" stroke-width="1.5"/>'
            + s.text(1332, 58, "дымоход (сущ.)", 10, "start"))
    s.item(1, "A6", body, leader=(1380, 160, 30, -40), title="Котёл; A6 — плата котла (OpenTherm)")
    # 2 separator with collector (collector ≥ sum of outlets — calc.py dn_collector)
    body = (f'<rect x="{sx}" y="{sy0}" width="36" height="{sy1 - sy0}" rx="8" fill="{eq_fill}" stroke="{fg}" stroke-width="1.8"/>'
            f'<rect x="480" y="{yS - 12}" width="{sx - 480}" height="24" fill="{eq_fill}" stroke="{fg}" stroke-width="1.5"/>'
            f'<rect x="480" y="{yR - 12}" width="{sx - 480}" height="24" fill="{eq_fill}" stroke="{fg}" stroke-width="1.5"/>'
            + s.text(640, yS + 4, "коллектор, подача (54×1,5)", 9) + s.text(640, yR + 4, "коллектор, обратка (54×1,5)", 9))
    s.item(2, "", body, leader=(sx + 18, 530, 40, 0), title="Гидрострелка с коллектором")
    # 3 DHW tank: coil, TEH, sleeve; recirculation into the middle third
    coil = " ".join(f"L{180 if i % 2 else 255},{yS + 5 + i * 9}" for i in range(10))
    body = (f'<rect x="140" y="360" width="120" height="400" rx="22" fill="{eq_fill}" stroke="{fg}" stroke-width="1.8"/>'
            f'<path d="M260,{yS} L255,{yS} {coil} L260,{yR}" fill="none" stroke="{fg}" stroke-width="1.3"/>'
            + s.text(200, 650, "БКН 200 л", 11, weight="bold") + s.text(200, 664, "змеевик 30 кВт", 9)
            + f'<path d="M150,730 l8,-8 l8,8 l8,-8 l8,8 l8,-8" fill="none" stroke="{fg}" stroke-width="1.5"/>'
            + s.text(205, 734, "EK1", 9, "start", "bold"))
    s.item(3, "EK1", body, leader=(255, 372, 25, -25), title="Бойлер косвенного нагрева с ТЭНом EK1")
    # 4 heating expansion tank on the boiler return, boiler side of the shut-off, lockable valve
    tx = BOILER_SIDE["tank_tee"]
    s.pipe("Т2", [(tx, yBR), (tx, 670)])
    s.item(26, "", s.valve(tx, 645, 90), leader=(tx + 8, 645, 22, 8), title="Кран с защитой от закрытия (под бак)")
    s.item(4, "", s.membrane_tank(tx, 670), leader=(tx, 714, 10, 30), title="Бак расширительный отопления")
    # 5 DHW expansion tank
    s.item(5, "", s.membrane_tank(300, 872, 22, 38), leader=(311, 894, 28, 10), title="Бак расширительный ГВС")
    # pumps
    s.item(6, "M1", s.pump(800, 350, -90) + s.text(822, 354, "M1", 10, "start", "bold"),
           leader=(806, 359, 60, 12), title="Насос радиаторов")
    s.item(7, "M2", s.pump(800, 700, 90) + s.text(822, 704, "M2", 10, "start", "bold"),
           leader=(806, 709, 60, 10), title="Насос тёплого пола")
    s.item(8, "M3", s.pump(405, yS, 180) + s.text(405, yS - 18, "M3", 10, weight="bold"),
           leader=(405, yS + 11, 10, 30), title="Насос загрузки БКН (скорость: ≤ 85 % расхода котла)")
    s.item(10, "M5", s.pump(95, 330, 90) + s.text(113, 334, "M5", 10, "start", "bold"),
           leader=(84, 330, -25, -20), title="Насос рециркуляции ГВС")
    # 9 well with its pump, 14 pressure tank with pressure switch SP1
    body = (f'<path d="M45,1062 V1135 M85,1062 V1135" stroke="{fg}" stroke-width="1.5"/>'
            + s.pump(65, 1100, -90) + s.text(92, 1132, "M4", 10, "start", "bold"))
    s.item(9, "M4", body, leader=(54, 1100, -12, 25), title="Скважинный насос")
    s.pipe("В1", [(115, 1030), (115, 1045)])
    body = (f'<rect x="93" y="1045" width="44" height="26" rx="13" fill="{eq_fill}" stroke="{fg}" stroke-width="1.3"/>'
            + s.text(115, 1062, "ГА", 9) + s.bubble(115, 1105, "PS") + s.text(130, 1109, "SP1", 9, "start", "bold")
            + f'<path d="M115,1071 V1094" fill="none" stroke="{fg}" stroke-width="1"/>')
    s.item(14, "SP1", body, leader=(137, 1058, 25, 0), title="Гидроаккумулятор с реле давления SP1 (в силовой цепи M4)")
    # 18 water treatment unit with its bypass
    body = (f'<rect x="300" y="1008" width="250" height="44" rx="4" fill="{eq_fill}" stroke="{fg}" stroke-width="1.4"/>'
            + s.text(425, 1024, "Водоподготовка: фильтр 100 мкм промывной (новый) →", 9)
            + s.text(425, 1036, "картриджи ПП 20 и 10 мкм (есть) → обезжелезивание", 9)
            + s.text(425, 1048, "и умягчитель — по анализу воды", 9)
            + f'<path d="M285,1030 V1000 H562 V1030" fill="none" stroke="{fg if s.gost else COLOURS["В1"]}" stroke-width="1.5"/>'
            + s.valve(425, 1000))
    s.item(18, "", body, leader=(425, 1052, 0, 30), title="Узел водоподготовки с обводом (состав — по анализу воды)")
    # 19 thermostatic DHW mixer
    s.item(19, "", s.mixer(170, 280), leader=(198, 280, 25, -20), title="Смеситель термостатический ГВС 50–55 °C")
    # 11, 12 mixing valves, 13 make-up valve
    s.item(11, "YA1", s.valve3(800, 410, "left") + s.text(830, 414, "YA1", 9, "start", "bold"),
           leader=(809, 416, 50, 10), title="Клапан трёхходовой радиаторов с приводом")
    s.item(12, "YA2", s.valve3(800, 640, "left") + s.text(830, 644, "YA2", 9, "start", "bold"),
           leader=(809, 634, 50, -10), title="Клапан трёхходовой тёплого пола с приводом")
    s.item(13, "YA3", s.motor_valve(MU, 760, 90, -1) + s.text(1255, 780, "YA3", 9, "end", "bold"),
           leader=(MU + 8, 760, 20, 0), title="Кран подпитки с электроприводом")
    # 15 radiators, 16 floor manifold with loops
    rads = "".join(f'<rect x="{x}" y="70" width="44" height="34" rx="3" fill="{eq_fill}" stroke="{fg}" stroke-width="1.3"/>'
                   + "".join(f'<path d="M{x + 6 + i * 8},74 V100" stroke="{fg}" stroke-width="1"/>' for i in range(5))
                   for x in (700, 758, 816))
    body = (rads + f'<path d="M722,104 V110 H838 V104 M780,104 V110" fill="none" stroke="{fg}" stroke-width="1.3"/>'
            + s.text(780, 60, "Радиаторы, 15 шт. × ~8 секций", 10))
    s.item(15, "", body, leader=(860, 85, 30, 0), title="Радиаторы")
    loops = "".join(f'<path d="M{708 + i * 50},912 c0,-12 30,-12 30,0 v6 c0,10 -24,10 -24,0" fill="none" stroke="{fg}" stroke-width="1"/>'
                    for i in range(3))
    body = (f'<rect x="700" y="900" width="160" height="30" rx="3" fill="{eq_fill}" stroke="{fg}" stroke-width="1.3"/>' + loops
            + s.text(780, 945, "Тёплый пол ≈ 80 м²", 10))
    s.item(16, "", body, leader=(860, 915, 30, -10), title="Коллектор тёплого пола с петлями")
    # 17 taps
    s.item(17, "", s.tap(30, 140) + s.text(30, 112, "ХВС", 11, weight="bold")
           + s.tap(170, 140) + s.text(170, 112, "ГВС", 11, weight="bold"),
           leader=(178, 130, 30, -15), title="Точки разбора")

    # ===== fittings =====
    # boiler supply (separator → boiler): valve 22, BK1, dial thermometer, safety group 20 nearest the boiler
    gx = BOILER_SIDE["safety_group"]
    body = (f'<path d="M{gx},{yBS} V365 M{gx},395 H{gx + 22}" stroke="{fg}" stroke-width="1.5"/>'
            + s.relief(gx, 415) + s.air_vent(gx, 365) + s.bubble(gx + 33, 395, "PI"))
    s.item(20, "", body, leader=(gx - 10, 365, -25, -25), title="Группа безопасности: клапан 3 бар, воздухоотводчик, манометр")
    s.item(22, "", s.valve(BOILER_SIDE["supply_valve"], yBS) + s.valve(BOILER_SIDE["return_valve"], yBR),
           leader=(BOILER_SIDE["supply_valve"], yBS + 6, 10, 30),
           title="Краны отсечки котла (группа безопасности, фильтр и бак — со стороны котла)")
    s.item(23, "", s.strainer(BOILER_SIDE["filter"], yBR), leader=(BOILER_SIDE["filter"], yBR + 7, -15, 30),
           title="Фильтр магнитный на обратке котла")
    # 24 shut-offs: each circuit at the collector and at its outlet; loading line both sides; cold to the tank
    v24 = (s.valve(800, 450, 90) + s.valve(760, 527, 90) + s.valve(800, 192, 90) + s.valve(760, 192, 90)       # radiators
           + s.valve(800, 527, 90) + s.valve(760, 610, 90) + s.valve(800, 875, 90) + s.valve(760, 875, 90)     # floor
           + s.valve(460, yS, 180) + s.valve(460, yR) + s.valve(280, yS, 180) + s.valve(280, yR)                # loading
           + s.valve(230, 960, 90) + s.valve(95, 440, 90))                                                      # cold, recirc
    s.item(24, "", v24, leader=(752, 527, -40, -20), title="Краны шаровые: контуры у коллектора и на выходе, загрузка БКН, ХВС к бойлеру, рециркуляция")
    # 25 check valves after the circuit pumps and the loading pump
    s.item(25, "", s.check(800, 295, -90) + s.check(800, 756, 90) + s.check(352, yS, 180),
           leader=(808, 295, 60, -10), title="Клапаны обратные после насосов")
    # 39 pump unions: every pump comes out between two of them
    s.item(39, "", s.union_valve(800, 378, -90) + s.union_valve(800, 322, -90) + s.union_valve(800, 672, 90)
           + s.union_valve(800, 728, 90) + s.union_valve(432, yS, 180) + s.union_valve(378, yS, 180)
           + s.union_valve(95, 300, 90) + s.union_valve(95, 360, 90),
           leader=(808, 322, 60, -14), title="Краны-американки насосов")
    # 48 check valves on the mixing-valve bypasses («ножка»)
    s.item(48, "", s.check(776, 410) + s.check(776, 640), leader=(776, 404, -30, -25),
           title="Обратные клапаны на перемычках смесительных узлов")
    s.item(27, "", s.air_vent(sx + 18, sy0) + s.air_vent(330, yS - 5), leader=(sx + 25, sy0 - 15, 25, -15),
           title="Воздухоотводчики: гидрострелка, верх линии загрузки БКН")
    s.pipe("Т2", [(sx + 18, sy1), (sx + 18, sy1 + 40)])
    s.item(28, "", s.drain(sx + 18, sy1 + 25, 90), leader=(sx + 26, sy1 + 25, 20, 10), title="Кран слива шлама ≥ 3/4\" в самой нижней точке")
    s.item(45, "", s.strainer(760, 790, -90), leader=(752, 790, -40, 10), title="Фильтр сетчатый на обратке тёплого пола")
    # make-up: valve, strainer, reducer, check (disconnector) → limiter → YA3; bypass with a valve
    s.item(29, "", s.valve(MU, 960, 90) + s.strainer(MU, 935, 90) + s.check(MU, 875, -90),
           leader=(MU + 8, 935, 25, 0), title="Подпитка: кран, фильтр, обратный клапан / дисконнектор")
    s.item(36, "", s.reducer(MU, 905, -90), leader=(MU + 10, 905, 22, 5), title="Редуктор давления подпитки 1,5 бар")
    s.item(37, "", s.needle(MU, 815, -90), leader=(MU - 8, 815, -30, 0), title="Дроссель — ограничение расхода подпитки")
    s.item(38, "", s.valve(1330, 775, 90), leader=(1338, 775, 20, 0), title="Обводной кран подпитки (заполнение, ремонт)")
    # BP1 and a dial gauge on a three-way gauge valve at the expansion-tank tee (neutral point)
    bx = BOILER_SIDE["bp1"]
    s.pipe("Т2", [(bx, yBR), (bx, 665)])
    s.item(40, "", s.valve(bx, 640, 90), leader=(bx - 8, 640, -22, 8), title="Кран трёхходовой под манометр")
    s.gauge(41, bx, 655, "left", "PI", dist=22, title="Манометр 0–4 бар (виден в ручном режиме)",
            leader=(bx - 33, 666, -10, 22))
    s.gauge(42, 1150, yBS, "up", "TI", dist=26, title="Термометр подачи котла", leader=(1161, 419, 15, -15))
    s.gauge(42, 800, 262, "right", "TI", dist=26, title="Термометр подачи радиаторов")
    s.gauge(42, 800, 812, "right", "TI", dist=26, title="Термометр подачи тёплого пола")
    s.item(30, "", s.check(95, 400, 90), leader=(103, 400, 20, 10), title="Обратный клапан рециркуляции")
    s.item(21, "", s.check(230, 925, -90) + s.relief(230, 900), leader=(222, 925, -40, -15),
           title="Узел безопасности бойлера: обратный клапан + клапан 6 бар")
    s.pipe("В1", [(230, 800), (262, 800)])
    s.item(43, "", s.drain(262, 800), leader=(262, 794, 15, -18), title="Кран слива бойлера (промывка, ТЭН, анод)")
    s.item(44, "", s.funnel(262, 912) + f'<path d="M246,900 H262 V900" fill="none" stroke="{fg}" stroke-width="0.8" stroke-dasharray="3 2"/>',
           leader=(271, 920, 20, 20), title="Воронка с разрывом струи: сбросы клапанов поз. 20, 21 в канализацию")
    # gas: inlet valve, thermal shut-off, solenoid, valve before the boiler, dielectric insert
    s.item(47, "", s.valve(1540, 960, 90), leader=(1532, 960, -25, 0), title="Кран газовый на вводе котельной")
    s.item(46, "", s.valve(1540, 925, 90) + s.text(1528, 929, "КТЗ", 8, "end"), leader=(1548, 925, 20, 0),
           title="Клапан термозапорный КТЗ")
    s.item(33, "YA4", s.motor_valve(1540, 880, 90, -1, "Э") + s.text(1502, 900, "YA4", 9, "end", "bold"),
           leader=(1546, 880, 20, 10), title="Клапан газовый электромагнитный отсечной")
    s.item(32, "", s.valve(1540, 470, 90), leader=(1546, 470, 20, 0), title="Кран газовый перед котлом")
    s.item(34, "", s.dielectric(1540, 420), leader=(1546, 420, 20, -10), title="Диэлектрическая вставка")
    body = (s.bubble(1570, 200, "QA") + s.text(1570, 180, "A5", 10, weight="bold")
            + f'<path d="M1570,211 V880 H1550" fill="none" stroke="{fg}" stroke-width="0.8" stroke-dasharray="4 3"/>')
    s.item(61, "A5", body, title="Сигнализатор загазованности CH4 + CO → отсечной клапан")

    # ===== instruments =====
    s.sensor(55, "BK1", "tsboiler_s", 1115, yBS, "up")
    s.sensor(55, "BK2", "tsboiler_b", 1150, yBR, "up")
    s.sensor(55, "BK3", "tsrad_s", 800, 228, "right")
    s.sensor(55, "BK4", "tsrad_b", 760, 228, "left")
    s.sensor(55, "BK5", "tsfloor_s", 800, 842, "right")
    s.sensor(55, "BK6", "tsfloor_b", 760, 842, "left")
    s.sensor(55, "BK7", "tsihb_s", 310, yS, "up", dist=34)
    s.sensor(55, "BK8", "tsihb_b", 320, yR, "down")
    s.sensor(55, "BK9", "tswatersupply_c", 265, 1030, "down", dist=24)
    s.sensor(55, "BK10", "tswatersupply_h", 230, 400, "right", dist=58, title="tswatersupply_h — гильза в верхней части бака")
    s.sensor(57, "BP1", "prs_heating", bx, 665, "down", "PT", dist=24, title="Давление отопления — у тройника расширительного бака")
    s.sensor(57, "BP2", "prs_water", 205, 1030, "down", "PT", dist=24, title="Давление воды — сразу после насоса скважины")
    s.sensor(62, "SK1", "50 °C", 800, 782, "right", "TSH", dist=30, title="Термостат накладной защиты тёплого пола")
    s.sensor(67, "SK2", "90 °C", 140, 700, "left", "TSA", dist=30, title="Аварийный термовыключатель ТЭНа, ручной взвод")


def legend(s: Sheet) -> None:
    lines = ["Т1 — подача отопления;  Т2 — обратка;  Т3 — ГВС;  Т4 — рециркуляция ГВС;  В1 — холодная вода;  Г1 — газ.",
             "TE — датчик DS18B20 в гильзе;  PT — датчик давления 0–5 бар;  PI — манометр;  TI — термометр;  PS — реле давления;",
             "TSH — термостат пола (отключает M2);  TSA — аварийный термовыключатель ТЭНа;  QA — сигнализатор загазованности.",
             "Число на полке — позиция по спецификации (03-specification.md); BK, M, YA… — обозначения на схемах подключений."]
    s.add(s.text(560, 1062, "Условные обозначения", 11, "start", "bold"))
    for i, line in enumerate(lines):
        s.add(s.text(560, 1080 + i * 15, line, 9.5, "start"))


def title_block(s: Sheet, name: str, sheet_no: str, w: int = W, h: int = H, rev: str = "Ред. 2 · 2026-10-17") -> None:
    fg = s.fg
    x0, y0 = w - 400, h - 110
    s.add(f'<rect x="10" y="10" width="{w - 20}" height="{h - 20}" fill="none" stroke="{fg}" stroke-width="1.5"/>')
    s.add(f'<g stroke="{fg}" stroke-width="1" fill="none"><rect x="{x0}" y="{y0}" width="390" height="100"/>'
          f'<path d="M{x0},{y0 + 30} H{x0 + 390} M{x0},{y0 + 60} H{x0 + 390} M{x0 + 300},{y0 + 30} V{y0 + 100} M{x0 + 180},{y0 + 60} V{y0 + 100}"/></g>')
    s.add(s.text(x0 + 195, y0 + 21, "HomeSite — котельная", 12, weight="bold"))
    s.add(s.text(x0 + 150, y0 + 50, name, 11, weight="bold"))
    s.add(s.text(x0 + 345, y0 + 50, f"Лист {sheet_no}", 10))
    s.add(s.text(x0 + 90, y0 + 85, rev, 10))
    s.add(s.text(x0 + 240, y0 + 85, "docs/boiler-room", 9))


def render(style: str) -> str:
    s = Sheet(style)
    draw(s)
    if s.gost:
        legend(s)
        title_block(s, "Схема обвязки принципиальная (А)", "2", PW, PH)
    else:
        title_block(s, "Схема котельной обзорная (B)", "1", PW, PH)
        s.add(s.text(560, 1075, "Красная — подача, синяя — обратка, розовая — ГВС, оранжевая — рециркуляция,", 10, "start"))
        s.add(s.text(560, 1090, "голубая — холодная вода, жёлтая — газ. Числа — позиции спецификации; вся арматура — на листе 2.", 10, "start"))
    body = "\n".join(s.out)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {PW} {PH}" width="{PW}" height="{PH}" '
            f'font-family="{FONT}">\n<rect width="{PW}" height="{PH}" fill="#fff"/>\n{body}\n</svg>\n')


def main() -> None:
    (HERE / "02-piping.svg").write_text(render("gost"), encoding="utf-8")
    (HERE / "01-overview.svg").write_text(render("color"), encoding="utf-8")


if __name__ == "__main__":
    main()
