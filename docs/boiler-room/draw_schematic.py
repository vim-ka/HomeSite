"""Controller schematic in KiCad style: logic side (sheet 7) and relay outputs with panel indicators (sheet 8).

Usage: python3 docs/boiler-room/draw_schematic.py   → writes 07e-controller-logic.svg, 07f-controller-power.svg

GPIO ↔ net assignments follow firmware/esp32-homesite/PINOUT.md (test_draw_schematic checks it); GPIO13 goes through
JP1 (relay K0 now, OpenTherm receive after the boiler swap), GPIO5 is OpenTherm transmit (relay K15 freed).
"""

from pathlib import Path
from xml.sax.saxutils import escape

from draw_piping import Sheet, title_block

HERE = Path(__file__).resolve().parent
SW, SH = 1700, 1200
FONT = "Arial, Helvetica, sans-serif"
WIRE, SYM, TXT, LBL = "#008400", "#840000", "#000000", "#000084"

# ESP32-DevKitC (38 pins): header J2 (left, top→bottom) and J3 (right, top→bottom)
DEVKIT_LEFT = ["3V3", "EN", "IO36", "IO39", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12",
               "GND", "IO13", "SD2", "SD3", "CMD", "5V"]
DEVKIT_RIGHT = ["GND", "IO23", "IO22", "TXD0", "RXD0", "IO21", "GND", "IO19", "IO18", "IO5", "IO17", "IO16", "IO4",
                "IO0", "IO2", "IO15", "SD1", "SD0", "CLK"]
PIN_NETS = {
    "3V3": "+3V3", "5V": "+5V", "GND": "GND",
    "IO39": "GAS", "IO34": "P_HEAT", "IO35": "P_WATER", "IO4": "1WIRE", "IO15": "DHT",
    "IO13": "K0/OT_RX", "IO5": "OT_TX",
    "IO12": "K1", "IO14": "K2", "IO27": "K3", "IO26": "K4", "IO25": "K5", "IO33": "K6", "IO32": "K7",
    "IO16": "K8", "IO17": "K9", "IO18": "K10", "IO19": "K11", "IO21": "K12", "IO22": "K13", "IO23": "K14",
}
NC_NOTES = {"EN": "кнопка EN на плате", "IO0": "кнопка BOOT на плате", "IO2": "светодиод платы", "TXD0": "USB платы",
            "RXD0": "USB платы", "IO36": "не исп. (ложные импульсы АЦП1)"}

# Relay outputs: channel, load, refs of the load chain, panel indicator, its label on the panel, colour
OUTPUTS = [
    (0, "ТА котла — сухой контакт (Beretta); после OpenTherm свободен", "", "", "", ""),
    (1, "M1 насос радиаторов", "M1", "HL4", "P1", "фиолетовый"),
    (2, "SK1 (NC 50 °C) → M2 насос тёплого пола", "SK1 M2", "HL5", "P2", "оранжевый"),
    (3, "M3 насос загрузки БКН", "M3", "HL6", "P3", "жёлтый"),
    (4, "катушка KM2 → (KM2 + SP1) → M4 насос скважины, QF6", "KM2 SP1 M4", "HL7", "WP", "синий"),
    (5, "M5 насос рециркуляции ГВС", "M5", "HL8", "RP", "тёмно-синий"),
    (6, "катушка KM1 → (KM1 + SK2) → EK1 ТЭН, QF5", "KM1 SK2 EK1", "HL9", "TEN", "бирюзовый"),
    (7, "YA3 кран подпитки — открыть", "YA3", "HL10", "АП", "красный"),
    (8, "YA3 кран подпитки — закрыть", "YA3", "HL11", "АП", "синий"),
    (9, "YA1 смесительный узел радиаторов — открыть", "YA1", "HL12", "СУ1", "красный"),
    (10, "YA1 смесительный узел радиаторов — закрыть", "YA1", "HL13", "СУ1", "синий"),
    (11, "YA2 смесительный узел тёплого пола — открыть", "YA2", "HL14", "СУ2", "красный"),
    (12, "YA2 смесительный узел тёплого пола — закрыть", "YA2", "HL15", "СУ2", "синий"),
    (13, "предупреждение (сама лампа HL1)", "", "HL1", "ALARM", "жёлтый"),
    (14, "HA1 зуммер — авария", "HA1", "HL2", "ALARM", "красный"),
    (15, "не используется: GPIO5 → OpenTherm (OT_TX)", "", "", "", ""),
]
# Two identical 8-channel boards (5 V coils): a failed board stops only its half. A2.1 — boiler, pumps, contactors;
# A2.2 — the three-point actuators (open and close of one valve on the same board) and the alarm lamps
RELAY_BOARDS = {"A2.1": [0, 1, 2, 3, 4, 5, 6, 15], "A2.2": [7, 8, 9, 10, 11, 12, 13, 14]}
BOARD_OF = {ch: board for board, chans in RELAY_BOARDS.items() for ch in chans}
COLOUR = {"красный": "#ef4444", "синий": "#3b82f6", "тёмно-синий": "#1e3a8a", "фиолетовый": "#7c3aed",
          "оранжевый": "#f59e0b", "жёлтый": "#facc15", "бирюзовый": "#14b8a6", "зелёный": "#22c55e"}


class Sch:
    def __init__(self):
        self.out: list[str] = []

    def add(self, s: str) -> None:
        self.out.append(s)

    @staticmethod
    def t(x, y, s, size=11, anchor="start", fill=TXT, weight="normal") -> str:
        return (f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" fill="{fill}" '
                f'font-weight="{weight}">{escape(s)}</text>')

    def wire(self, *pts) -> None:
        d = "M" + " L".join(f"{x},{y}" for x, y in pts)
        self.add(f'<path d="{d}" fill="none" stroke="{WIRE}" stroke-width="1.6"/>')

    def dot(self, x, y) -> None:
        self.add(f'<circle cx="{x}" cy="{y}" r="3" fill="{WIRE}"/>')

    def part(self, refs: str, body: str, pos=None) -> None:
        attrs = f' data-ref="{refs}"' if refs else ""
        attrs += f' data-pos="{pos}"' if pos else ""
        self.add(f"<g{attrs}>{body}</g>")

    # --- power symbols, net labels ---
    def vcc(self, x, y, name) -> None:
        self.add(f'<path d="M{x},{y} V{y - 12} M{x - 8},{y - 12} H{x + 8}" stroke="{SYM}" stroke-width="1.6" fill="none"/>'
                 + self.t(x, y - 17, name, 10, "middle", SYM, "bold"))

    def gnd(self, x, y) -> None:
        self.add(f'<path d="M{x},{y} V{y + 10} M{x - 9},{y + 10} H{x + 9} M{x - 6},{y + 14} H{x + 6} M{x - 3},{y + 18} H{x + 3}" '
                 f'stroke="{SYM}" stroke-width="1.6" fill="none"/>')

    def label(self, x, y, name, right=True) -> None:
        """Net label at the end of a wire: a flag pointing away from (x, y)."""
        w = 8 + 7 * len(name)
        if right:
            pts = f"{x},{y} {x + 6},{y - 8} {x + w},{y - 8} {x + w},{y + 8} {x + 6},{y + 8}"
            tx, anchor = x + 9, "start"
        else:
            pts = f"{x},{y} {x - 6},{y - 8} {x - w},{y - 8} {x - w},{y + 8} {x - 6},{y + 8}"
            tx, anchor = x - 9, "end"
        self.add(f'<polygon points="{pts}" fill="#fff" stroke="{LBL}" stroke-width="1"/>' + self.t(tx, y + 4, name, 10, anchor, LBL, "bold"))

    def nc(self, x, y) -> None:
        self.add(f'<path d="M{x - 5},{y - 5} L{x + 5},{y + 5} M{x - 5},{y + 5} L{x + 5},{y - 5}" stroke="#0000c8" stroke-width="1.4"/>')

    # --- passive parts (body strings) ---
    def resistor(self, x, y, vertical, ref, value) -> str:
        r = (f'<rect x="{x - 5}" y="{y - 15}" width="10" height="30" fill="#fffff0" stroke="{SYM}" stroke-width="1.5"/>'
             if vertical else f'<rect x="{x - 15}" y="{y - 5}" width="30" height="10" fill="#fffff0" stroke="{SYM}" stroke-width="1.5"/>')
        if vertical:
            return r + self.t(x + 9, y - 2, ref, 10, fill=SYM, weight="bold") + self.t(x + 9, y + 10, value, 9)
        return r + self.t(x, y - 9, ref + "  " + value, 9, "middle", SYM)

    def capacitor(self, x, y, ref, value, polar=False) -> str:
        """Vertical capacitor centred at (x, y)."""
        body = (f'<path d="M{x - 10},{y - 3} H{x + 10} M{x - 10},{y + 3} H{x + 10}" stroke="{SYM}" stroke-width="2"/>')
        if polar:
            body += self.t(x - 14, y - 4, "+", 10, "middle", SYM)
        return body + self.t(x + 13, y - 2, ref, 10, fill=SYM, weight="bold") + self.t(x + 13, y + 10, value, 9)

    def zener(self, x, y, ref, value) -> str:
        """Vertical zener / TVS, cathode up, centred at (x, y)."""
        return (f'<path d="M{x - 7},{y + 6} H{x + 7} L{x},{y - 6} Z" fill="none" stroke="{SYM}" stroke-width="1.5"/>'
                f'<path d="M{x - 9},{y - 9} L{x - 7},{y - 6} H{x + 7} L{x + 9},{y - 3}" fill="none" stroke="{SYM}" stroke-width="1.5"/>'
                + self.t(x + 13, y - 2, ref, 10, fill=SYM, weight="bold") + self.t(x + 13, y + 10, value, 9))

    def terminal(self, x, y, ref, pins, note, pitch=20) -> tuple[str, list[tuple[int, int]]]:
        """Screw terminal block: pins on its left edge at (x, y + i·pitch); returns body and pin points."""
        h = pitch * len(pins)
        body = (f'<rect x="{x}" y="{y - pitch / 2}" width="70" height="{h}" fill="#fffff0" stroke="{SYM}" stroke-width="1.5"/>'
                + self.t(x + 35, y - pitch / 2 - 5, ref, 10, "middle", SYM, "bold"))
        pts = []
        for i, name in enumerate(pins):
            py = y + i * pitch
            body += (f'<circle cx="{x}" cy="{py}" r="3" fill="#fff" stroke="{SYM}" stroke-width="1.2"/>'
                     + self.t(x + 8, py + 4, f"{i + 1} {name}", 9, fill=SYM))
            pts.append((x, py))
        body += self.t(x, y + h - pitch / 2 + 14, note, 9.5)       # caption under the block
        return body, pts


def frame(s: Sch, name: str, sheet_no: str, notes: list[str]) -> str:
    g = Sheet("gost")
    for i, line in enumerate(notes):
        g.add(g.text(30, SH - 95 + i * 15, line, 9.5, "start"))
    title_block(g, name, sheet_no, SW, SH)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SW} {SH}" width="{SW}" height="{SH}" font-family="{FONT}">\n'
            f'<rect width="{SW}" height="{SH}" fill="#fff"/>\n' + "\n".join(s.out + g.out) + "\n</svg>\n")


# ------------------------------------------------------------------------------------------------
def devkit(s: Sch, x0=720, y0=190, pitch=30, nets=PIN_NETS, notes=NC_NOTES,
           title="A1  ESP32-DevKitC (ESP32-WROOM-32)", sub="прошивка esp32-homesite", ref="A1", pos=50) -> None:
    w = 260
    body = (f'<rect x="{x0}" y="{y0 - 30}" width="{w}" height="{pitch * 19 + 30}" fill="#ffffe0" stroke="{SYM}" stroke-width="2"/>'
            + Sch.t(x0 + w / 2, y0 - 38, title, 12, "middle", SYM, "bold")
            + Sch.t(x0 + w / 2, y0 + pitch * 19 + 16, sub, 9, "middle"))
    for side, pins in (("L", DEVKIT_LEFT), ("R", DEVKIT_RIGHT)):
        for i, name in enumerate(pins):
            y = y0 + i * pitch
            if side == "L":
                px, ex, nx, anchor = x0, x0 - 30, x0 + 6, "start"
            else:
                px, ex, nx, anchor = x0 + w, x0 + w + 30, x0 + w - 6, "end"
            body += (f'<path d="M{px},{y} H{ex}" stroke="{SYM}" stroke-width="1.6"/>'
                     + Sch.t((px + ex) / 2, y - 4, f"{'J2' if side == 'L' else 'J3'}-{i + 1}", 8, "middle", SYM)
                     + Sch.t(nx, y + 4, name, 10, anchor, TXT))
    s.part(ref, body, pos)
    for side, pins in (("L", DEVKIT_LEFT), ("R", DEVKIT_RIGHT)):
        for i, name in enumerate(pins):
            y = y0 + i * pitch
            ex = x0 - 30 if side == "L" else x0 + w + 30
            net = nets.get(name)
            if net == "+3V3" or net == "+5V":
                s.wire((ex, y), (ex - 20 if side == "L" else ex + 20, y))
                s.vcc(ex - 20 if side == "L" else ex + 20, y, net)
            elif net == "GND":
                s.wire((ex, y), (ex - 20 if side == "L" else ex + 20, y))
                s.gnd(ex - 20 if side == "L" else ex + 20, y)
            elif net:
                s.wire((ex, y), (ex - 14 if side == "L" else ex + 14, y))
                s.label(ex - 14 if side == "L" else ex + 14, y, net, right=(side == "R"))
            else:
                s.nc(ex, y)
                if name in notes:
                    s.add(Sch.t(ex - 10 if side == "L" else ex + 10, y + 4, notes[name], 8.5,
                                "end" if side == "L" else "start", "#555"))


def pullup_input(s: Sch, y, net, rref, rval, xref, pins, note, pos_r, pos_x, x_node=250, data_pin=1) -> None:
    """net label → node with a pull-up to +3V3 → the terminal's data pin (index `data_pin`) at height y."""
    s.label(90, y, net, right=True)
    s.wire((90 + 8 + 7 * len(net), y), (x_node, y), (440, y))
    s.dot(x_node, y)
    s.wire((x_node, y), (x_node, y - 20))
    s.part(rref, s.resistor(x_node, y - 35, True, rref, rval), pos_r)
    s.wire((x_node, y - 50), (x_node, y - 62))
    s.vcc(x_node, y - 62, "+3V3")
    body, pts = s.terminal(440, y - 20 * data_pin, xref, pins, note)
    s.part(xref, body, pos_x)


def render_logic() -> str:
    s = Sch()
    devkit(s)
    # --- left: sensor inputs ---
    s.add(Sch.t(40, 70, "Входы датчиков", 12, weight="bold"))
    # 1-Wire bus: terminal pins +3V3 / DATA / GND, DATA in the middle (y)
    pullup_input(s, 150, "1WIRE", "R1", "4,7 кОм", "X2", ["+3V3", "DATA", "GND"], "→ BK1…BK10 DS18B20 (гирлянда)", 69, 69)
    s.wire((440, 130), (420, 130)); s.vcc(420, 130, "+3V3")
    s.wire((440, 170), (420, 170)); s.gnd(420, 170)
    pullup_input(s, 290, "DHT", "R2", "10 кОм", "X3", ["+3V3", "DATA", "GND"], "→ BK11 DHT22 (strapping GPIO15)", 69, 69)
    s.wire((440, 270), (420, 270)); s.vcc(420, 270, "+3V3")
    s.wire((440, 310), (420, 310)); s.gnd(420, 310)
    # pressure sensors: sensor SIG → R (series) → node with C and zener to GND → GPIO label
    for y, net, r, c, vd, x, bp in ((440, "P_HEAT", "R3", "C3", "VD1", "X4", "BP1 prs_heating"),
                                    (580, "P_WATER", "R4", "C4", "VD2", "X5", "BP2 prs_water")):
        s.label(90, y, net, right=True)
        s.wire((90 + 8 + 7 * len(net), y), (300, y))
        for xc, part in ((190, "C"), (240, "VD")):
            s.dot(xc, y)
            s.wire((xc, y), (xc, y + 22))
            s.wire((xc, y + 38), (xc, y + 50))
            s.gnd(xc, y + 50)
        s.part(c, s.capacitor(190, y + 30, c, "100 нФ"), 69)
        s.part(vd, s.zener(240, y + 30, vd, "3,6 В"), 69)
        s.part(r, s.resistor(330, y, False, r, "10 кОм"), 69)
        s.wire((345, y), (440, y))
        body, pts = s.terminal(440, y - 20, x, ["+5V", "SIG", "GND"], f"→ {bp} (YD4060, 0–3,3 В)")
        s.part(x, body, 69)
        s.wire((440, y - 20), (420, y - 20)); s.vcc(420, y - 20, "+5V")
        s.wire((440, y + 20), (420, y + 20)); s.gnd(420, y + 20)
    # gas alarm dry contact: pull-up, RC, contact to GND
    pullup_input(s, 760, "GAS", "R5", "10 кОм", "X6", ["CONT", "GND"], "→ A5 сухой контакт аварии (опрос)", 69, 69,
                 x_node=200, data_pin=0)
    s.wire((300, 760), (300, 782)); s.dot(300, 760)
    s.part("C5", s.capacitor(300, 790, "C5", "100 нФ"), 69)
    s.wire((300, 798), (300, 810)); s.gnd(300, 810)
    s.wire((440, 780), (420, 780)); s.gnd(420, 780)
    # power input
    s.add(Sch.t(40, 880, "Питание", 12, weight="bold"))
    body, pts = s.terminal(90, 920, "X1", ["+5V", "GND"], "")
    s.part("X1", body, 69)
    s.add(Sch.t(90, 975, "← G1 БП 5 В ≥ 3 А (поз. 54)", 9.5))
    s.part("G1", Sch.t(90, 990, "G1", 10, fill=SYM, weight="bold"), 54)
    s.wire((90, 920), (60, 920)); s.vcc(60, 920, "+5V")
    s.wire((90, 940), (60, 940)); s.gnd(60, 940)
    for xc, ref, val, polar in ((300, "C1", "100 мкФ", True), (380, "C2", "100 нФ", False)):
        s.vcc(xc, 910, "+5V"); s.wire((xc, 910), (xc, 927))
        s.part(ref, s.capacitor(xc, 935, ref, val, polar), 69)
        s.wire((xc, 943), (xc, 955)); s.gnd(xc, 955)
    s.add(Sch.t(240, 1000, "+3V3 — стабилизатор платы A1 (≤ 300 мА на внешнее)", 9.5))

    # --- right: relay module inputs, JP1, OpenTherm adapter ---
    x0, pitch = 1330, 22
    for board, y0 in (("A2.1", 190), ("A2.2", 470)):
        chans = RELAY_BOARDS[board]
        pins = ["VCC", "JD-VCC"] + [f"IN{i + 1}" for i in range(8)] + ["GND"]
        body = (f'<rect x="{x0}" y="{y0 - 16}" width="190" height="{pitch * len(pins) + 10}" fill="#ffffe0" stroke="{SYM}" stroke-width="2"/>'
                + Sch.t(x0 + 95, y0 - 24, f"{board}  модуль реле 8 кан. (вход)", 11, "middle", SYM, "bold"))
        for i, name in enumerate(pins):
            y = y0 + i * pitch
            body += f'<path d="M{x0},{y} H{x0 - 25}" stroke="{SYM}" stroke-width="1.6"/>' + Sch.t(x0 + 6, y + 4, name, 10)
        s.part(board, body, 51)
        for i, name in enumerate(pins):
            y, ex = y0 + i * pitch, x0 - 25
            if name == "VCC":
                s.wire((ex, y), (ex - 30, y)); s.vcc(ex - 30, y, "+3V3")
            elif name == "JD-VCC":
                s.wire((ex, y), (ex - 70, y)); s.vcc(ex - 70, y, "+5V")
            elif name == "GND":
                s.wire((ex, y), (ex - 20, y)); s.gnd(ex - 20, y)
            elif chans[int(name[2:]) - 1] == 15:
                s.nc(ex, y); s.add(Sch.t(ex - 10, y + 4, "K15 свободен (GPIO5 → OT_TX)", 8.5, "end", "#555"))
            else:
                ch = chans[int(name[2:]) - 1]
                s.wire((ex, y), (ex - 12, y)); s.label(ex - 12, y, f"K{ch}", right=False)
    s.add(Sch.t(x0 + 95, 730, "выходы K0…K15 → лист 8", 9, "middle"))
    s.add(Sch.t(1100, 186, "перемычку VCC–JD-VCC снять:", 9, fill="#555") + Sch.t(1100, 200, "вход 3,3 В, катушки 5 В", 9, fill="#555"))
    # JP1: GPIO13 to relay K0 (now) or OpenTherm receive (after the boiler swap)
    jx, jy = 1150, 760
    body = (f'<rect x="{jx}" y="{jy - 15}" width="34" height="80" fill="#fffff0" stroke="{SYM}" stroke-width="1.5"/>'
            + Sch.t(jx + 17, jy - 22, "JP1", 10, "middle", SYM, "bold"))
    for i in range(3):
        body += f'<circle cx="{jx + 17}" cy="{jy + i * 25}" r="4" fill="#fff" stroke="{SYM}" stroke-width="1.3"/>' + Sch.t(jx + 40, jy + i * 25 + 4, str(i + 1), 9, fill=SYM)
    s.part("JP1", body, 69)
    for i, net in enumerate(("K0", "K0/OT_RX", "OT_RX")):
        s.wire((jx + 13, jy + i * 25), (jx - 10, jy + i * 25))
        s.label(jx - 10, jy + i * 25, net, right=False)
    s.add(Sch.t(jx + 60, jy + 4, "1–2: реле котла K0 (сейчас, Beretta)", 9.5)
          + Sch.t(jx + 60, jy + 54, "2–3: приём OpenTherm (после замены котла)", 9.5))
    # X7: OpenTherm adapter A3
    body, pts = s.terminal(1330, 880, "X7", ["+3V3", "GND", "OUT", "IN"], "→ A3 адаптер OpenTherm → котёл (лист 5)")
    s.part("X7", body, 69)
    s.part("A3", Sch.t(1330, 965, "A3", 10, fill=SYM, weight="bold"), 52)
    s.wire((1330, 880), (1310, 880)); s.vcc(1310, 880, "+3V3")
    s.wire((1330, 900), (1310, 900)); s.gnd(1310, 900)
    s.wire((1330, 920), (1300, 920)); s.label(1300, 920, "OT_RX", right=False)
    s.wire((1330, 940), (1300, 940)); s.label(1300, 940, "OT_TX", right=False)
    return frame(s, "Контроллер: схема принципиальная (логика)", "7", [
        "Цепи с одинаковыми метками соединены. Позиции R, C, VD, X, JP — поз. 69 спецификации; A1, A2.1, A2.2, A3, G1 — поз. 50–54.",
        "GPIO12 (K1) — загрузочный вывод: если модуль реле тянет его вверх при включении, ESP32 не загрузится (flash 1,8 В) — один раз",
        "записать eFuse: espefuse.py --port COMx set_flash_voltage 3.3V. GPIO36/39 — без прерываний (errata АЦП1); GPIO13 — через JP1.",
        "A2.1, A2.2 — одинаковые: перемычку VCC–JD-VCC снять, VCC = +3V3, JD-VCC = +5V; GND общий. Платы на ULN2803 (HIGH = вкл.) — только 5V/GND, в портале снять «инверсию реле»."])


# ------------------------------------------------------------------------------------------------
def lamp(s: Sch, x, y, ref, label, colour) -> str:
    """Panel indicator (ГОСТ: lamp circle with a cross), filled with its colour; caption to the right."""
    c = COLOUR.get(colour, "#fff")
    return (f'<circle cx="{x}" cy="{y}" r="9" fill="{c}" stroke="{SYM}" stroke-width="1.5"/>'
            f'<path d="M{x - 6},{y - 6} L{x + 6},{y + 6} M{x - 6},{y + 6} L{x + 6},{y - 6}" stroke="{SYM}" stroke-width="1.2"/>'
            + f'<rect x="{x + 12}" y="{y - 8}" width="{len(ref + label + colour) * 7 + 30}" height="16" fill="#fff"/>'
            + Sch.t(x + 16, y + 4, f"{ref}  {label} · {colour}", 9.5, fill=SYM, weight="bold"))


def render_power() -> str:
    s = Sch()
    lx, nx, top, step = 110, 1560, 190, 52
    s.add(Sch.t(40, 70, "Выходы реле A2.1, A2.2 → нагрузки; индикатор панели — параллельно нагрузке (230 В)", 12, weight="bold"))
    s.add(Sch.t(lx - 20, 110, "L′ от QF4 (C10) через ИБП G2", 10, fill=LBL, weight="bold") + Sch.t(nx + 10, 110, "N", 10, fill=LBL, weight="bold"))
    s.part("QF4", Sch.t(lx - 20, 125, "QF4", 9, fill=SYM), 60)
    s.wire((lx, 115), (lx, top + 15 * step + 10))
    s.wire((nx, 85), (nx, top + 15 * step + 10))
    # boiler power line with PB indicator
    s.wire((lx - 60, 145), (330, 145))
    s.add(Sch.t(lx - 95, 141, "L", 10, fill=LBL, weight="bold"))
    s.part("QF2", f'<rect x="{lx - 50}" y="138" width="40" height="14" fill="#fffff0" stroke="{SYM}"/>' + Sch.t(lx - 30, 135, "QF2 C6", 9, "middle", SYM), 60)
    s.part("A6", f'<rect x="360" y="134" width="300" height="22" fill="#fffff0" stroke="{SYM}" stroke-width="1.4"/>'
                 + Sch.t(370, 149, "A6 котёл — питание 230 В (через ИБП)", 10), 1)
    s.wire((330, 145), (360, 145)); s.wire((660, 145), (nx, 145)); s.dot(nx, 145)
    s.dot(330, 145); s.wire((330, 145), (330, 165), (990, 165))
    s.wire((1009, 165), (nx, 165)); s.dot(nx, 165)
    s.part("HL3", lamp(s, 1000, 165, "HL3", "PB", "зелёный"), 68)
    for ch, load, refs, hl, label, colour in OUTPUTS:
        y = top + ch * step + 20
        # relay contact COM → NO
        s.dot(lx, y)
        s.wire((lx, y), (170, y))
        s.part(BOARD_OF[ch], f'<circle cx="170" cy="{y}" r="2.5" fill="{SYM}"/><path d="M170,{y} L205,{y - 12}" stroke="{SYM}" stroke-width="1.8"/>'
                     f'<circle cx="210" cy="{y}" r="2.5" fill="{SYM}"/>' + Sch.t(160, y - 10, f"K{ch}", 10, "end", SYM, "bold")
                     + Sch.t(160, y + 12, BOARD_OF[ch], 8, "end", SYM), 51)
        if ch in (0, 15):
            s.wire((210, y), (260, y))
            s.add(Sch.t(268, y + 4, load, 10))
            continue
        s.wire((210, y), (300, y))
        s.part("XT1", f'<circle cx="300" cy="{y}" r="4" fill="#fff" stroke="{SYM}" stroke-width="1.2"/>' + Sch.t(300, y - 8, f"XT1:{ch}", 8, "middle", SYM), 63)
        if refs:
            s.wire((304, y), (360, y))
            s.part(refs, f'<rect x="360" y="{y - 11}" width="540" height="22" fill="#fffff0" stroke="{SYM}" stroke-width="1.4"/>'
                         + Sch.t(370, y + 4, load, 10), None)
            s.wire((900, y), (nx, y)); s.dot(nx, y)
            # indicator in parallel with the load
            s.dot(330, y)
            s.wire((330, y), (330, y + 20), (990, y + 20))
            s.wire((1009, y + 20), (nx, y + 20)); s.dot(nx, y + 20)
            s.part(hl, lamp(s, 1000, y + 20, hl, label, colour), 68 if hl not in ("HL1", "HL2") else 59)
        else:                                   # the lamp is the load itself (HL1 warning)
            s.wire((304, y), (990, y))
            s.wire((1009, y), (nx, y)); s.dot(nx, y)
            s.part(hl, lamp(s, 1000, y, hl, label, colour), 59)
            s.add(f'<rect x="1245" y="{y - 8}" width="240" height="16" fill="#fff"/>' + Sch.t(1250, y + 4, "— " + load, 9.5))
    return frame(s, "Выходы реле и индикаторы панели (230 В)", "8", [
        "Индикаторы панели — светодиодные 230 В (поз. 68), включены параллельно нагрузке после контакта реле: горят, когда реле подало фазу.",
        "Для ТЭНа и скважины индикатор параллелен катушке контактора (показывает команду); SK2 и SP1 стоят в силовой цепи контакторов (лист 3).",
        "SK1 размыкает питание M2 и его индикатора при перегреве пола. ALARM на панели — HL1 (жёлтый, предупреждение) и HL2 (красный, авария).",
        "K0 — сухой контакт на клеммы ТА котла (не 230 В), поэтому PB показывает питание котла (после QF2). SA1 «Р» подаёт L′ на M1 и M2 в обход K1, K2."])


def main() -> None:
    (HERE / "07e-controller-logic.svg").write_text(render_logic(), encoding="utf-8")
    (HERE / "07f-controller-power.svg").write_text(render_power(), encoding="utf-8")


if __name__ == "__main__":
    main()
