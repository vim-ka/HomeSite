"""Boiler room piping drawings from one topology.

Usage: python3 docs/boiler-room/draw_piping.py   → writes 02-piping.svg (A, GOST style) and 01-overview.svg (B, colour)

Coordinates are one sheet 1400 × 900; the boiler stands on the right as in the real room (and on the site's scheme).
Every item carries data-pos (specification position) and, for electrical parts, data-ref (ГОСТ 2.710 code) —
check_docs.py cross-checks them with 03-specification.md.
"""

from pathlib import Path
from xml.sax.saxutils import escape

HERE = Path(__file__).resolve().parent
W, H = 1400, 900
FONT = "Arial, Helvetica, sans-serif"

# Fittings left out of the colour overview (they only clutter it)
SMALL = {"20", "21", "22", "23", "24", "25", "26", "27", "28", "29", "30", "32", "34"}

# x of the fittings on the boiler pipes (boiler on the right: larger x = boiler side). The safety group and the
# expansion tank must stay connected to the boiler when its shut-off valves are closed.
BOILER_SIDE = {"supply_valve": 960, "safety_group": 1040, "return_valve": 1100, "tank_tee": 1170}

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

    # ===== pipelines (drawn first, equipment over them) =====
    # boiler ↔ separator
    s.pipe("Т1", [(1150, 320), (1150, 380), (916, 380)], codes=[(1150, 352)])
    s.pipe("Т2", [(916, 460), (1230, 460), (1230, 320)], codes=[(1230, 400)])
    # radiators: supply riser x 800 up, return riser x 760 down to the return collector
    s.pipe("Т1", [(800, 370), (800, 110)], codes=[(800, 135)])
    s.pipe("Т2", [(760, 110), (760, 450)], codes=[(760, 135)])
    s.pipe("Т2", [(760, 330), (791, 330)])                       # radiator bypass into the valve
    # floor: supply riser x 800 down (crossing the return collector), return riser x 760 up
    s.pipe("Т1", [(800, 390), (800, 700)], codes=[(800, 685)])
    s.pipe("Т2", [(760, 700), (760, 470)], codes=[(760, 685)])
    s.pipe("Т2", [(760, 505), (791, 505)])                       # floor bypass
    # tank loading: collector → pump → coil → back
    s.pipe("Т1", [(440, 380), (260, 380)], codes=[(290, 380)])
    s.pipe("Т2", [(260, 460), (440, 460)], codes=[(290, 460)])
    # DHW and recirculation
    s.pipe("Т3", [(170, 280), (170, 140)], codes=[(170, 235)])
    s.pipe("Т4", [(170, 200), (95, 200), (95, 560), (140, 560)], codes=[(95, 480)])
    # cold water: well → main → cold tap, tank, make-up
    s.pipe("В1", [(65, 800), (65, 760), (940, 760)], codes=[(520, 760)])
    s.pipe("В1", [(65, 760), (30, 760), (30, 140)], codes=[(30, 600)])
    s.pipe("В1", [(230, 760), (230, 620)])
    s.pipe("В1", [(230, 655), (290, 655), (290, 668)])           # to the DHW expansion tank
    s.pipe("В1", [(940, 760), (940, 560), (898, 560), (898, 520)], codes=[(919, 560)])
    # gas
    s.pipe("Г1", [(1300, 760), (1300, 345), (1190, 345), (1190, 320)], codes=[(1300, 690)])

    # ===== equipment =====
    # 1 boiler + chimney
    body = (f'<rect x="1120" y="110" width="140" height="210" rx="6" fill="{eq_fill}" stroke="{fg}" stroke-width="1.8"/>'
            + s.text(1190, 205, "Котёл газовый", 12, weight="bold") + s.text(1190, 221, "настенный, 28 кВт", 10)
            + s.text(1190, 235, "открытая камера, OT", 10)
            + f'<path d="M1180,110 V30 M1200,110 V30" stroke="{fg}" stroke-width="1.5"/>'
            + s.text(1212, 58, "дымоход (сущ.)", 10, "start"))
    s.item(1, "A6", body, leader=(1260, 140, 30, -40), title="Котёл; A6 — плата котла (OpenTherm)")
    # 2 hydraulic separator with collector
    body = (f'<rect x="880" y="340" width="36" height="180" rx="8" fill="{eq_fill}" stroke="{fg}" stroke-width="1.8"/>'
            f'<rect x="440" y="370" width="440" height="20" fill="{eq_fill}" stroke="{fg}" stroke-width="1.5"/>'
            f'<rect x="440" y="450" width="440" height="20" fill="{eq_fill}" stroke="{fg}" stroke-width="1.5"/>'
            + s.text(660, 384, "коллектор, подача", 9) + s.text(660, 464, "коллектор, обратка", 9))
    s.item(2, "", body, leader=(898, 430, 40, 0), title="Гидрострелка с коллектором")
    # 3 DHW tank with coil and TEH
    coil = " ".join(f"L{180 if i % 2 else 255},{385 + i * 9}" for i in range(9))
    body = (f'<rect x="140" y="280" width="120" height="340" rx="22" fill="{eq_fill}" stroke="{fg}" stroke-width="1.8"/>'
            f'<path d="M260,380 L255,380 {coil} L260,460" fill="none" stroke="{fg}" stroke-width="1.3"/>'
            + s.text(200, 530, "БКН 200 л", 11, weight="bold") + s.text(200, 544, "змеевик 30 кВт", 9)
            + f'<path d="M150,590 l8,-8 l8,8 l8,-8 l8,8 l8,-8" fill="none" stroke="{fg}" stroke-width="1.5"/>'
            + s.text(205, 594, "EK1", 9, "start", "bold"))
    s.item(3, "EK1", body, leader=(140, 300, -20, -30), title="Бойлер косвенного нагрева с ТЭНом EK1")
    # 4 heating expansion tank on the return, behind a lockable valve
    tx = BOILER_SIDE["tank_tee"]
    s.pipe("Т2", [(tx, 460), (tx, 540)])
    s.item(26, "", s.valve(tx, 505, 90), leader=(tx - 8, 505, -25, 0), title="Кран с защитой от закрытия (под бак)")
    s.item(4, "", s.membrane_tank(tx, 540), leader=(tx - 13, 570, -30, 20), title="Бак расширительный отопления")
    # 5 DHW expansion tank
    s.item(5, "", s.membrane_tank(290, 668, 22, 38), leader=(301, 690, 28, 10), title="Бак расширительный ГВС")
    # pumps
    s.item(6, "M1", s.pump(800, 285, -90) + s.text(822, 289, "M1", 10, "start", "bold"),
           leader=(806, 294, 45, 15), title="Насос радиаторов")
    s.item(7, "M2", s.pump(800, 550, 90) + s.text(822, 554, "M2", 10, "start", "bold"),
           leader=(806, 559, 45, 12), title="Насос тёплого пола")
    s.item(8, "M3", s.pump(410, 380, 180) + s.text(410, 362, "M3", 10, weight="bold"),
           leader=(410, 391, 10, 30), title="Насос загрузки БКН")
    s.item(10, "M5", s.pump(95, 330, 90) + s.text(113, 334, "M5", 10, "start", "bold"),
           leader=(84, 330, -25, -20), title="Насос рециркуляции ГВС")
    # 9 well with its pump, 14 pressure tank
    body = (f'<path d="M45,800 V880 M85,800 V880" stroke="{fg}" stroke-width="1.5"/>'
            + s.pump(65, 840, -90) + s.text(92, 848, "M4", 10, "start", "bold")
            + s.text(65, 795, "", 9))
    s.item(9, "M4", body, leader=(54, 840, -12, 30), title="Скважинный насос")
    s.pipe("В1", [(130, 760), (130, 780)])
    body = (f'<rect x="108" y="780" width="44" height="26" rx="13" fill="{eq_fill}" stroke="{fg}" stroke-width="1.3"/>'
            + s.text(130, 797, "ГА", 9))
    s.item(14, "", body, leader=(130, 806, 10, 24), title="Гидроаккумулятор с реле давления")
    # 11, 12 mixing valves, 13 make-up valve
    s.item(11, "YA1", s.valve3(800, 330, "left") + s.text(830, 334, "YA1", 9, "start", "bold"),
           leader=(809, 336, 32, 14), title="Клапан трёхходовой радиаторов с приводом")
    s.item(12, "YA2", s.valve3(800, 505, "left") + s.text(830, 509, "YA2", 9, "start", "bold"),
           leader=(809, 499, 32, -14), title="Клапан трёхходовой тёплого пола с приводом")
    s.item(13, "YA3", s.motor_valve(940, 650, 90, 1) + s.text(972, 654, "YA3", 9, "start", "bold"),
           leader=(932, 650, -30, 15), title="Кран подпитки с электроприводом")
    # 15 radiators, 16 floor manifold with loops
    rads = "".join(f'<rect x="{x}" y="70" width="44" height="34" rx="3" fill="{eq_fill}" stroke="{fg}" stroke-width="1.3"/>'
                   + "".join(f'<path d="M{x + 6 + i * 8},74 V100" stroke="{fg}" stroke-width="1"/>' for i in range(5))
                   for x in (700, 758, 816))
    body = (rads + f'<path d="M722,104 V110 H838 V104 M780,104 V110" fill="none" stroke="{fg}" stroke-width="1.3"/>'
            + s.text(780, 60, "Радиаторы, 15 шт. × ~8 секций", 10))
    s.item(15, "", body, leader=(860, 85, 30, 0), title="Радиаторы")
    loops = "".join(f'<path d="M{708 + i * 50},712 c0,-12 30,-12 30,0 v6 c0,10 -24,10 -24,0" fill="none" stroke="{fg}" stroke-width="1"/>'
                    for i in range(3))
    body = (f'<rect x="700" y="700" width="160" height="30" rx="3" fill="{eq_fill}" stroke="{fg}" stroke-width="1.3"/>' + loops
            + s.text(780, 745, "Тёплый пол ≈ 80 м²", 10))
    s.item(16, "", body, leader=(860, 715, 30, -10), title="Коллектор тёплого пола с петлями")
    # 17 taps
    s.item(17, "", s.tap(30, 140) + s.text(30, 112, "ХВС", 11, weight="bold")
           + s.tap(170, 140) + s.text(170, 112, "ГВС", 11, weight="bold"),
           leader=(178, 130, 30, -15), title="Точки разбора")

    # ===== fittings =====
    # 20 safety group on the boiler supply: stem with relief valve, air vent and gauge
    gx = BOILER_SIDE["safety_group"]
    body = (f'<path d="M{gx},380 V300 M{gx},330 H{gx + 22}" stroke="{fg}" stroke-width="1.5"/>'
            + s.relief(gx, 350) + s.air_vent(gx, 300) + s.bubble(gx + 33, 330, "PI"))
    s.item(20, "", body, leader=(1030, 300, -25, -25), title="Группа безопасности: клапан 3 бар, воздухоотводчик, манометр")
    s.item(22, "", s.valve(BOILER_SIDE["supply_valve"], 380) + s.valve(BOILER_SIDE["return_valve"], 460),
           leader=(BOILER_SIDE["supply_valve"], 385, 12, 30), title="Краны отсечки котла (группа безопасности и бак — со стороны котла)")
    s.item(23, "", s.strainer(1040, 460), leader=(1040, 467, 15, 25), title="Фильтр магнитный/сетчатый на обратке котла")
    # 24 circuit shut-offs (radiators, floor, cold to the tank)
    s.item(24, "", s.valve(800, 220, 90) + s.valve(760, 220, 90) + s.valve(800, 640, 90) + s.valve(760, 640, 90)
           + s.valve(230, 735, 90), leader=(752, 640, -50, -15), title="Краны шаровые на контурах")
    # 25 check valves after the circuit pumps and the loading pump
    s.item(25, "", s.check(800, 250, -90) + s.check(800, 585, 90) + s.check(375, 380, 180),
           leader=(808, 250, 40, -10), title="Клапаны обратные")
    s.item(27, "", s.air_vent(898, 340), leader=(905, 325, 25, -15), title="Воздухоотводчик гидрострелки")
    s.pipe("Т2", [(916, 505), (950, 505)])
    s.item(28, "", s.drain(950, 505), leader=(950, 499, 10, -20), title="Кран слива")
    s.item(29, "", s.valve(940, 735, 90) + s.strainer(940, 705, 90) + s.check(940, 680, -90),
           leader=(948, 705, 30, 0), title="Подпитка: кран, фильтр, обратный клапан")
    s.item(30, "", s.check(95, 400, 90), leader=(103, 400, 20, 10), title="Обратный клапан рециркуляции")
    s.item(21, "", s.check(230, 700, -90) + s.relief(230, 675), leader=(222, 700, -40, -15),
           title="Узел безопасности бойлера: обратный клапан + клапан 6 бар")
    # gas: dielectric insert, ball valve, solenoid shut-off
    s.item(34, "", s.dielectric(1300, 400), leader=(1306, 400, 25, -10), title="Диэлектрическая вставка")
    s.item(32, "", s.valve(1300, 450, 90), leader=(1306, 450, 25, 0), title="Кран газовый шаровой")
    s.item(33, "YA4", s.motor_valve(1300, 520, 90, -1, "Э") + s.text(1262, 540, "YA4", 9, "end", "bold"),
           leader=(1306, 520, 25, 10), title="Клапан газовый электромагнитный отсечной")
    body = (s.bubble(1340, 200, "QA") + s.text(1340, 180, "A5", 10, weight="bold")
            + f'<path d="M1340,211 V520 H1310" fill="none" stroke="{fg}" stroke-width="0.8" stroke-dasharray="4 3"/>')
    s.item(61, "A5", body, leader=(1351, 200, 15, -35), title="Сигнализатор загазованности CH4 + CO → отсечной клапан")

    # ===== instruments =====
    s.sensor(55, "BK1", "tsboiler_s", 1005, 380, "up")
    s.sensor(55, "BK2", "tsboiler_b", 1005, 460, "down")
    s.sensor(55, "BK3", "tsrad_s", 800, 185, "right")
    s.sensor(55, "BK4", "tsrad_b", 760, 185, "left")
    s.sensor(55, "BK5", "tsfloor_s", 800, 668, "right")
    s.sensor(55, "BK6", "tsfloor_b", 760, 668, "left")
    s.sensor(55, "BK7", "tsihb_s", 320, 380, "up")
    s.sensor(55, "BK8", "tsihb_b", 320, 460, "down")
    s.sensor(55, "BK9", "tswatersupply_c", 170, 760, "up", dist=26)
    s.sensor(55, "BK10", "tswatersupply_h", 230, 300, "right", dist=58, title="tswatersupply_h — гильза в верхней части бака")
    s.sensor(57, "BP1", "prs_heating", 940, 600, "right", "PT", title="Давление отопления — труба подпитки под гидрострелкой")
    s.sensor(57, "BP2", "prs_water", 195, 760, "down", "PT", dist=24, title="Давление воды — сразу после насоса скважины")
    s.sensor(62, "SK1", "50 °C", 800, 612, "right", "TSH", dist=34, title="Термостат накладной защиты тёплого пола")


def legend(s: Sheet) -> None:
    lines = ["Т1 — подача отопления;  Т2 — обратка;  Т3 — ГВС;  Т4 — рециркуляция ГВС;  В1 — холодная вода;  Г1 — газ.",
             "TE — датчик температуры DS18B20 в гильзе;  PT — датчик давления 0–5 бар;  PI — манометр;",
             "TSH — термостат накладной (отключает насос пола);  QA — сигнализатор загазованности.",
             "Число на полке — позиция по спецификации (03-specification.md); BK, M, YA… — обозначения на схемах подключений."]
    s.add(s.text(330, 800, "Условные обозначения", 11, "start", "bold"))
    for i, line in enumerate(lines):
        s.add(s.text(330, 818 + i * 15, line, 9.5, "start"))


def title_block(s: Sheet, name: str, sheet_no: str) -> None:
    fg = s.fg
    s.add(f'<rect x="10" y="10" width="{W - 20}" height="{H - 20}" fill="none" stroke="{fg}" stroke-width="1.5"/>')
    s.add(f'<g stroke="{fg}" stroke-width="1" fill="none"><rect x="1000" y="790" width="390" height="100"/>'
          '<path d="M1000,820 H1390 M1000,850 H1390 M1300,820 V890 M1180,850 V890"/></g>')
    s.add(s.text(1195, 811, "HomeSite — котельная", 12, weight="bold"))
    s.add(s.text(1150, 840, name, 11, weight="bold"))
    s.add(s.text(1345, 840, f"Лист {sheet_no}", 10))
    s.add(s.text(1090, 875, "Ред. 1 · 2026-10-17", 10))
    s.add(s.text(1240, 875, "docs/boiler-room", 9))
    s.add(s.text(1345, 875, "", 9))


def render(style: str) -> str:
    s = Sheet(style)
    draw(s)
    if s.gost:
        legend(s)
        title_block(s, "Схема обвязки принципиальная (А)", "2")
    else:
        title_block(s, "Схема котельной обзорная (B)", "1")
        s.add(s.text(330, 815, "Красная — подача, синяя — обратка, розовая — ГВС, оранжевая — рециркуляция,", 10, "start"))
        s.add(s.text(330, 830, "голубая — холодная вода, жёлтая — газ. Числа — позиции спецификации; арматура — на листе 2.", 10, "start"))
    body = "\n".join(s.out)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'font-family="{FONT}">\n<rect width="{W}" height="{H}" fill="#fff"/>\n{body}\n</svg>\n')


def main() -> None:
    (HERE / "02-piping.svg").write_text(render("gost"), encoding="utf-8")
    (HERE / "01-overview.svg").write_text(render("color"), encoding="utf-8")


if __name__ == "__main__":
    main()
