"""Wiring drawings: structure (sheet 3), sensors (sheet 4), boiler and OpenTherm (sheet 5), RF gateway (sheet 6).

Usage: python3 docs/boiler-room/draw_wiring.py   → writes 07a-structure.svg, 07b-sensors.svg, 07c-boiler-opentherm.svg,
       07d-rf-gateway.svg

Relay channels and GPIO follow firmware/esp32-homesite/PINOUT.md (test_draw_wiring checks it).
"""

from pathlib import Path

from draw_piping import FONT, H, W, Sheet, title_block
from draw_schematic import RELAY_BOARDS

HERE = Path(__file__).resolve().parent

# channel, GPIO, load (text), refs of what it switches
RELAYS = [
    (0, 13, "освобождён: GPIO13 → приём OpenTherm (лист 5)", ""),
    (1, 12, "M1 насос радиаторов", "M1"),
    (2, 14, "SK1 (NC, 50 °C) → M2 насос тёплого пола", "SK1 M2"),
    (3, 27, "M3 насос загрузки БКН", "M3"),
    (4, 26, "катушка KM2 → M4 насос скважины", "KM2 M4"),
    (5, 25, "M5 насос рециркуляции ГВС", "M5"),
    (6, 33, "катушка KM1 → EK1 ТЭН", "KM1 EK1"),
    (7, 32, "YA3 кран подпитки — открыть", "YA3"),
    (8, 16, "YA3 кран подпитки — закрыть", "YA3"),
    (9, 17, "YA1 клапан радиаторов — открыть", "YA1"),
    (10, 18, "YA1 клапан радиаторов — закрыть", "YA1"),
    (11, 19, "YA2 клапан тёплого пола — открыть", "YA2"),
    (12, 21, "YA2 клапан тёплого пола — закрыть", "YA2"),
    (13, 22, "HL1 лампа «Предупреждение»", "HL1"),
    (14, 23, "HL2 лампа «Авария» + HA1 зуммер", "HL2 HA1"),
    (15, 5, "свободен: GPIO5 → передача OpenTherm (лист 5)", ""),
]


def box(s: Sheet, pos, ref, x, y, w, h, title, sub="", fill=None) -> str:
    """A device block; the body string is returned for s.item()."""
    body = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" fill="{fill or s.bg}" stroke="{s.fg}" stroke-width="1.5"/>'
            + s.text(x + w / 2, y + 16, title, 11, weight="bold"))
    if sub:
        body += s.text(x + w / 2, y + 30, sub, 9)
    return body


def wire(s: Sheet, pts, label="", at=None, dash=False, width=1.2) -> None:
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    extra = ' stroke-dasharray="5 4"' if dash else ""
    s.add(f'<path d="{d}" fill="none" stroke="{s.fg}" stroke-width="{width}"{extra}/>')
    if label:
        x, y = at or pts[0]
        s.add(s.text(x, y, label, 9, "start"))


def resistor(s: Sheet, x, y, vertical=True) -> str:
    return (f'<rect x="{x - 4}" y="{y - 10}" width="8" height="20" fill="{s.bg}" stroke="{s.fg}" stroke-width="1.2"/>' if vertical
            else f'<rect x="{x - 10}" y="{y - 4}" width="20" height="8" fill="{s.bg}" stroke="{s.fg}" stroke-width="1.2"/>')


def capacitor(s: Sheet, x, y) -> str:
    """Capacitor on a vertical lead to ground at (x, y)."""
    return (f'<path d="M{x - 7},{y - 2} H{x + 7} M{x - 7},{y + 2} H{x + 7}" stroke="{s.fg}" stroke-width="1.6"/>')


def finish(s: Sheet, name: str, sheet_no: str, notes: list[str]) -> str:
    for i, line in enumerate(notes):
        s.add(s.text(30, 806 + i * 15, line, 9.5, "start"))
    title_block(s, name, sheet_no)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
            f'font-family="{FONT}">\n<rect width="{W}" height="{H}" fill="#fff"/>\n' + "\n".join(s.out) + "\n</svg>\n")


# ------------------------------------------------------------------------------------------------
def render_structure() -> str:
    s = Sheet("gost")
    # input and the main bus
    s.add(s.text(60, 60, "Ввод 230 В, 50 Гц (L, N, PE)", 11, "start", "bold"))
    s.item(60, "QF1", box(s, 60, "QF1", 60, 75, 120, 40, "QF1", "C32, без УЗО"))
    wire(s, [(120, 115), (120, 720)], width=2)
    # UPS-backed branch
    wire(s, [(120, 150), (250, 150)])
    s.item(64, "G2", box(s, 64, "G2", 250, 125, 130, 50, "G2 ИБП для котлов", "синус, N–PE на выходе"))
    wire(s, [(380, 150), (420, 150), (420, 520)], width=2)
    s.add(s.text(426, 145, "L′ (через ИБП)", 9, "start"))
    rows = [(250, "QF2", "C6", "котёл A6 (лист 5)"), (330, "QF3", "C6", "автоматика"), (500, "QF4", "C10", "насосы, приводы — общий L на реле")]
    for y, ref, rating, what in rows:
        wire(s, [(420, y), (450, y)])
        s.item(60, ref, box(s, 60, ref, 450, y - 18, 70, 36, ref, rating))
    wire(s, [(520, 250), (600, 250)], "→ A6 L, N, PE", (528, 243))
    # automation fed from QF3
    wire(s, [(520, 330), (560, 330), (560, 440)])
    s.item(54, "G1", box(s, 54, "G1", 580, 312, 110, 36, "G1 БП 5 В", "≥ 3 А"))
    wire(s, [(560, 330), (580, 330)])
    s.item(53, "A4", box(s, 53, "A4", 580, 360, 110, 36, "A4 RF-шлюз", "433 МГц, Wi‑Fi"))
    wire(s, [(560, 378), (580, 378)])
    s.item(61, "A5", box(s, 61, "A5", 580, 408, 110, 36, "A5 сигнализатор", "CH₄ + CO"))
    wire(s, [(560, 426), (580, 426)])
    wire(s, [(635, 348), (635, 360)])
    wire(s, [(690, 330), (720, 330), (720, 600), (640, 600)], "5 В", (724, 470))
    # controller
    s.item(50, "A1", box(s, 50, "A1", 470, 580, 170, 120, "A1 ESP32", "esp32-homesite")
           + s.text(555, 640, "GPIO → K0…K15 (шлейф)", 9) + s.text(555, 655, "датчики — лист 4", 9)
           + s.text(555, 670, "OpenTherm — лист 5", 9))
    wire(s, [(640, 650), (760, 650)], "16 линий + 5 В, GND", (646, 643))
    # QF4 feeds relay commons
    wire(s, [(520, 500), (740, 500), (740, 160), (760, 160)])
    s.add(s.text(528, 493, "общий L → COM реле K0…K15", 9, "start"))
    # relay modules: two identical 8-channel boards, rows in board order
    top, step = 140, 38
    by_ch = {ch: (gpio, load, refs) for ch, gpio, load, refs in RELAYS}
    order = RELAY_BOARDS["A2.1"] + RELAY_BOARDS["A2.2"]
    for b, board in enumerate(("A2.1", "A2.2")):
        y_top = top + b * 8 * step
        body = box(s, 51, board, 760, y_top - 2, 210, 8 * step - 4, "", "")
        cy = y_top + 4 * step
        body += (f'<text x="750" y="{cy}" font-size="10" font-weight="bold" text-anchor="middle" fill="{s.fg}" '
                 f'transform="rotate(-90 750 {cy})">{board} — реле 8 кан., 5 В</text>')
        for r in range(8):
            ch = order[b * 8 + r]
            y = top + 20 + (b * 8 + r) * step
            body += (s.text(772, y + 4, f"K{ch}", 10, "start", "bold") + s.text(812, y + 4, f"GPIO{by_ch[ch][0]}", 9, "start")
                     + f'<path d="M880,{y} l12,-6 M892,{y} H970" stroke="{s.fg}" stroke-width="1.2"/>'
                     + f'<circle cx="880" cy="{y}" r="2" fill="{s.fg}"/>')
        s.item(51, board, body)
    # terminal strip and loads
    s.item(63, "XT1", f'<rect x="990" y="150" width="22" height="{16 * step + 10}" fill="{s.bg}" stroke="{s.fg}" stroke-width="1.2"/>'
           + s.text(1001, 143, "XT1", 10, weight="bold"))
    for r, ch in enumerate(order):
        _, load, refs = by_ch[ch]
        y = top + 20 + r * step
        wire(s, [(970, y), (1030, y)])
        body = s.text(1036, y + 4, load, 10, "start")
        if refs:
            first = refs.split()[0]
            pos = {"M1": 6, "SK1": 62, "M3": 8, "KM2": 65, "M5": 10, "KM1": 58, "YA3": 13, "YA1": 11, "YA2": 12,
                   "HL1": 59, "HL2": 59}[first]
            s.item(pos, refs, body)
        else:
            s.add(body)
    # contactor-switched loads (no UPS)
    wire(s, [(120, 600), (150, 600)])
    s.item(60, "QF5", box(s, 60, "QF5", 150, 582, 80, 36, "QF5", "C16, 30 мА"))
    wire(s, [(230, 600), (250, 600)])
    s.item(58, "KM1", box(s, 58, "KM1", 250, 582, 60, 36, "KM1", "25 А"))
    wire(s, [(310, 600), (330, 600)])
    s.item(67, "SK2", box(s, 67, "SK2", 330, 582, 60, 36, "SK2", "90 °C, взвод"))
    wire(s, [(390, 600), (400, 600)])
    s.item(3, "EK1", s.text(404, 604, "EK1", 10, "start", "bold"))
    wire(s, [(120, 680), (150, 680)])
    s.item(60, "QF6", box(s, 60, "QF6", 150, 662, 80, 36, "QF6", "C16, 30 мА"))
    wire(s, [(230, 680), (250, 680)])
    s.item(65, "KM2", box(s, 65, "KM2", 250, 662, 60, 36, "KM2", "25 А"))
    wire(s, [(310, 680), (330, 680)])
    s.item(14, "SP1", box(s, 14, "SP1", 330, 662, 60, 36, "SP1", "реле давл."))
    wire(s, [(390, 680), (400, 680)])
    s.item(9, "M4", s.text(404, 684, "M4", 10, "start", "bold"))
    s.add(s.text(150, 728, "KM1 → SK2 → EK1: ТЭН (SK2 — аварийный термовыключатель бака, ручной взвод)", 9, "start"))
    s.add(s.text(150, 742, "KM2 → SP1 → M4: насос скважины (реле давления ГА — последовательно)", 9, "start"))
    s.add(s.text(150, 756, "катушки KM1, KM2 — от реле K6, K4 (справа)", 9, "start"))
    return finish(s, "Схема электрическая структурная", "3", [
        "N и PE каждой нагрузки — на шины XT1; реле A2.1, A2.2 коммутируют только фазу. ТЭН и насос скважины — через контакторы",
        "(пусковой ток мотора и ток ТЭНа не для реле 10 А), без ИБП, каждая со своим УЗО 30 мА. Котёл, насосы, приводы, автоматика — через ИБП G2.",
        "Приводы YA1–YA3 трёхточечные: два реле на привод, одновременно не включаются (прошивка). SK1 размыкает питание M2 при > 50 °C.",
        "Каналы K0 и K15 освобождены: их GPIO13 и GPIO5 — приём и передача OpenTherm (лист 5)."])


# ------------------------------------------------------------------------------------------------
SENSOR_TRACE = [("BK1", "tsboiler_s", "котёл, подача"), ("BK2", "tsboiler_b", "котёл, обратка"),
                ("BK3", "tsrad_s", "радиаторы, подача"), ("BK4", "tsrad_b", "радиаторы, обратка"),
                ("BK5", "tsfloor_s", "пол, подача"), ("BK6", "tsfloor_b", "пол, обратка"),
                ("BK7", "tsihb_s", "БКН, подача"), ("BK8", "tsihb_b", "БКН, обратка"),
                ("BK10", "tswatersupply_h", "бак, верх. гильза"), ("BK9", "tswatersupply_c", "ХВС после насоса")]


def render_sensors() -> str:
    s = Sheet("gost")
    pins = [("3V3", 150), ("GND", 175), ("5V (VIN)", 200), ("GPIO4", 260), ("GPIO15", 470), ("GPIO34", 530),
            ("GPIO35", 610), ("GPIO39", 690)]
    body = box(s, 50, "A1", 60, 110, 170, 620, "A1 ESP32")
    for name, y in pins:
        body += s.text(222, y + 4, name, 10, "end", "bold") + f'<circle cx="230" cy="{y}" r="2.5" fill="{s.fg}"/>'
    s.item(50, "A1", body)
    s.item(54, "G1", box(s, 54, "G1", 60, 60, 170, 36, "G1 БП 5 В") )
    wire(s, [(145, 96), (145, 110)])
    # 1-Wire bus: 3V3, DATA, GND rails
    rail = {"3V3": 240, "DATA": 260, "GND": 280}
    wire(s, [(230, 150), (250, 150), (250, 240), (1330, 240)], "3,3 В", (1290, 235))
    wire(s, [(230, 260), (1330, 260)], "DATA", (1290, 255))
    wire(s, [(230, 175), (240, 175), (240, 280), (1330, 280)], "GND", (1290, 295))
    s.add(resistor(s, 290, 250) + s.text(298, 232, "4,7 кОм — одна на шину", 9, "start"))
    for i, (ref, name, where) in enumerate(SENSOR_TRACE):
        x = 360 + i * 92
        body = "".join(f'<path d="M{x + dx},{rail[r]} V320" stroke="{s.fg}" stroke-width="1"/><circle cx="{x + dx}" cy="{rail[r]}" r="2" fill="{s.fg}"/>'
                       for dx, r in ((-12, "3V3"), (0, "DATA"), (12, "GND")))
        body += (f'<rect x="{x - 26}" y="320" width="52" height="30" rx="3" fill="{s.bg}" stroke="{s.fg}" stroke-width="1.3"/>'
                 + s.text(x, 339, ref, 10, weight="bold") + s.text(x, 366, name, 8.5) + s.text(x, 378, where, 8.5))
        s.item(55, ref, body)
    s.add(s.text(360, 405, "DS18B20 (поз. 55) гирляндой по трассе: один кабель от A1 до последнего датчика, отводы ≤ 0,3 м, без «звезды».", 9.5, "start"))
    s.add(s.text(360, 420, "Кабель — витая пара FTP cat.5e (DATA + GND в одной паре), экран на GND со стороны A1; 3 провода, паразитное питание не применять.", 9.5, "start"))
    # DHT22
    wire(s, [(230, 470), (520, 470)])
    s.add(resistor(s, 330, 455) + s.text(330, 440, "3,3 В", 9) + s.text(340, 459, "10 кОм (обязательно: GPIO15 — strapping)", 9, "start"))
    s.item(56, "BK11", box(s, 56, "BK11", 520, 452, 150, 36, "BK11 DHT22", "воздух котельной"))
    # pressure sensors
    for ref, gpio_y, name, where in (("BP1", 530, "prs_heating", "подпитка у гидрострелки"), ("BP2", 610, "prs_water", "после насоса скважины")):
        wire(s, [(230, gpio_y), (380, gpio_y)])
        s.add(resistor(s, 330, gpio_y, vertical=False) + s.text(330, gpio_y - 10, "10 кОм", 9))
        wire(s, [(380, gpio_y), (380, gpio_y + 14)])
        s.add(capacitor(s, 380, gpio_y + 16) + s.text(392, gpio_y + 22, "100 нФ → GND", 9, "start"))
        wire(s, [(380, gpio_y), (520, gpio_y)], "сигнал 0–3,3 В", (420, gpio_y - 5))
        s.item(57, ref, box(s, 57, ref, 520, gpio_y - 22, 230, 44, f"{ref} YD4060", f"{name} — {where}"))
        wire(s, [(750, gpio_y - 8), (800, gpio_y - 8)], "+5 В (G1)", (804, gpio_y - 5))
        wire(s, [(750, gpio_y + 8), (800, gpio_y + 8)], "GND (общий с A1)", (804, gpio_y + 12))
    # gas alarm dry contact
    wire(s, [(230, 690), (520, 690)])
    s.add(resistor(s, 440, 675) + s.text(440, 660, "3,3 В", 9) + s.text(448, 679, "10 кОм", 9, "start"))
    s.add(capacitor(s, 400, 706) + s.text(370, 724, "100 нФ → GND", 9))
    wire(s, [(400, 690), (400, 704)])
    s.item(61, "A5", box(s, 61, "A5", 520, 668, 180, 44, "A5 «сухой» контакт аварии", "замыкает на GND при газе / CO"))
    s.add(s.text(720, 694, "предложение для прошивки: вход аварии газа (GPIO39 — input-only, внешняя подтяжка)", 9, "start"))
    return finish(s, "Схема подключения датчиков", "4", [
        "GPIO34/35/39 — АЦП1/вход без внутренней подтяжки; АЦП2 при Wi‑Fi не работает — поэтому давление на 34/35.",
        "GPIO39 (как и 36) ловит ложные импульсы при работе АЦП1 (errata ESP32) — вход аварии газа только опросом с антидребезгом, без прерываний.",
        "Датчики давления: питание 5 В, выход уже 0–3,3 В — делитель не нужен. Калибровка — PINOUT.md и раздел 8.",
        "Сигнальные кабели вести отдельно от 230 В (≥ 10 см или в отдельном лотке); экраны — на GND только со стороны A1."])


# ------------------------------------------------------------------------------------------------
def render_boiler() -> str:
    s = Sheet("gost")
    # controller and OT adapter
    body = box(s, 50, "A1", 60, 270, 170, 180, "A1 ESP32")
    for name, y in (("3V3", 320), ("GND", 345), ("GPIO13 (вход)", 380), ("GPIO5 (выход)", 410)):
        body += s.text(222, y + 4, name, 10, "end", "bold")
    s.item(50, "A1", body)
    body = box(s, 52, "A3", 370, 270, 180, 170, "A3 адаптер OpenTherm", "опторазвязка, без полярности")
    for name, y in (("3V3", 320), ("GND", 345), ("OUT (приём)", 380), ("IN (передача)", 410)):
        body += s.text(378, y + 4, name, 10, "start")
    body += s.text(542, 364, "OT", 10, "end", "bold") + s.text(542, 394, "OT", 10, "end", "bold")
    s.item(52, "A3", body)
    for y in (320, 345):
        wire(s, [(230, y), (370, y)])
    wire(s, [(370, 380), (230, 380)], "приём → GPIO13", (250, 375))
    wire(s, [(230, 410), (370, 410)], "GPIO5 → передача", (250, 405))
    # manual mode switch on the OT pair
    body = box(s, 66, "SA1", 640, 300, 140, 150, "SA1 «Авто / Ручной»", "3 полюса")
    body += (f'<circle cx="665" cy="350" r="3" fill="{s.fg}"/><circle cx="665" cy="375" r="3" fill="{s.fg}"/>'
             f'<circle cx="755" cy="362" r="3" fill="{s.fg}"/><path d="M755,362 L668,351" stroke="{s.fg}" stroke-width="1.6"/>'
             + s.text(677, 343, "А", 9, "start") + s.text(677, 392, "Р", 9, "start")
             + s.text(710, 415, "Р: OT1 котла → перемычка на OT2", 8.5) + s.text(710, 435, "SA1.2, SA1.3 — текст ниже", 8.5))
    s.item(66, "SA1", body)
    wire(s, [(550, 360), (600, 360), (600, 350), (665, 350)])
    wire(s, [(665, 375), (652, 375), (652, 400)], dash=True)
    wire(s, [(550, 390), (620, 390), (620, 400), (850, 400), (850, 385), (900, 385)], "OT2", (860, 380))
    wire(s, [(755, 362), (830, 362), (830, 350), (900, 350)], "OT1", (860, 345))
    s.add(s.text(560, 470, "OT: витая пара 2×0,75, ≤ 50 м, отдельно от 230 В. Клеммы котла — ТА / OpenTherm (одни и те же — проверить в паспорте).", 9.5, "start"))
    # boiler
    body = box(s, 1, "A6", 900, 150, 260, 300, "Котёл (поз. 1), плата A6")
    for name, y in (("L", 200), ("N", 225), ("PE", 250), ("OT1 / ТА", 350), ("OT2 / ТА", 385)):
        body += s.text(910, y + 4, name, 10, "start", "bold")
    body += s.text(1030, 290, "Wi‑Fi производителя — только на", 9) + s.text(1030, 303, "отдельном разъёме, не на OT (раздел 5.3)", 9)
    s.item(1, "A6", body)
    # power via UPS
    s.item(64, "G2", box(s, 64, "G2", 380, 150, 130, 50, "G2 ИБП", "от QF1"))
    wire(s, [(510, 175), (600, 175)])
    s.item(60, "QF2", box(s, 60, "QF2", 600, 157, 70, 36, "QF2", "C6"))
    wire(s, [(670, 175), (720, 175), (720, 200), (900, 200)], "L", (880, 195))
    wire(s, [(720, 225), (900, 225)], "N", (880, 220))
    wire(s, [(720, 250), (900, 250)], "PE", (880, 245))
    s.add(s.text(714, 238, "N, PE — шины XT1 (через ИБП)", 9, "end"))
    s.add(s.text(726, 270, "фазировка по паспорту (L — к L котла)", 9, "start"))
    # manual mode: pumps bypass
    s.add(s.text(60, 540, "SA1 в положении «Р» (контроллер неисправен): котёл греет по своей уставке (ручка), SA1.2 подаёт L′ на M1,", 10, "start"))
    s.add(s.text(60, 556, "SA1.3 — на SK1 → M2 в обход реле K1, K2; трёхходовые клапаны выставить вручную (рычаг привода). Котёл без насосов контуров", 10, "start"))
    s.add(s.text(60, 572, "грел бы только гидрострелку — поэтому ручной режим включает и насосы.", 10, "start"))
    # gas safety
    s.item(61, "A5", box(s, 61, "A5", 380, 620, 200, 60, "A5 сигнализатор", "CH₄ под потолком, CO 1,5–1,8 м"))
    s.item(33, "YA4", box(s, 33, "YA4", 700, 620, 200, 60, "YA4 клапан газовый", "НО, ручной взвод, на вводе"))
    wire(s, [(580, 650), (700, 650)], "импульс «закрыть»", (595, 643))
    wire(s, [(480, 680), (480, 720), (230, 720)], "сухой контакт → A1 GPIO39 (лист 4)", (240, 714))
    return finish(s, "Котёл: питание, OpenTherm, резервный режим", "5", [
        "Нормальный режим (SA1 «А»): уставки котла задаёт A1 по OpenTherm через A3. Приём — GPIO13, не GPIO36/39: на них при работе",
        "АЦП1 (датчики давления) бывают ложные импульсы (errata ESP32), а библиотека OT принимает по прерываниям.",
        "Если у выбранного котла OT и ТА — разные клеммы: перемычку «Р» подать на ТА, OT оставить на A3.",
        "Котёл, A1, A3, насосы — от ИБП G2: при отключении сети котёл с открытой камерой продолжает работать."])


# ------------------------------------------------------------------------------------------------
# CC1101 pin → ESP32 GPIO, as firmware/esp32-rf-gateway/PINOUT.md (test_draw_wiring checks it)
RF_PINS = {"SCK": 18, "MISO": 19, "MOSI": 23, "CSN": 5, "GDO0": 4, "GDO2": 2}


def render_rf_gateway() -> str:
    s = Sheet("gost")
    rows = [("3V3", "VCC", 260, "питание только 3,3 В"), ("GND", "GND", 300, "")] + [
        (f"GPIO{RF_PINS[k]}", k if k != "MISO" else "MISO (GDO1)", y, what)
        for k, y, what in (("SCK", 340, "SPI clock"), ("MISO", 380, "SPI MISO"), ("MOSI", 420, "SPI MOSI"),
                           ("CSN", 460, "chip select"), ("GDO0", 500, "данные: демодулированный поток (прерывания)"),
                           ("GDO2", 540, "не используется (RSSI) — можно не подключать"))]
    esp = box(s, 53, "A4", 60, 220, 240, 400, "A4.1 ESP32 DevKit", "прошивка esp32-rf-gateway")
    cc = box(s, 53, "A4", 760, 220, 220, 400, "A4.2 CC1101", "433,92 МГц, OOK")
    for gpio, pin, y, what in rows:
        esp += s.text(292, y + 4, gpio, 10, "end", "bold") + f'<circle cx="300" cy="{y}" r="2.5" fill="{s.fg}"/>'
        cc += s.text(768, y + 4, pin, 10, "start", "bold") + f'<circle cx="760" cy="{y}" r="2.5" fill="{s.fg}"/>'
    esp += s.text(180, 585, "GPIO0 — кнопка BOOT (5 с — сброс настроек)", 8.5) + s.text(180, 600, "GPIO2 — светодиод платы", 8.5)
    cc += s.text(970, 284, "ANT", 10, "end", "bold") + f'<circle cx="980" cy="280" r="2.5" fill="{s.fg}"/>'
    # power, antenna
    body = esp + cc + box(s, 53, "A4", 60, 110, 240, 50, "Блок питания USB 5 В, ≥ 1 А", "в разъём USB платы ESP32")
    s.item(53, "A4", body, title="RF-шлюз: ESP32 + CC1101")
    wire(s, [(180, 160), (180, 220)], "USB 5 В", (186, 196))
    for gpio, pin, y, what in rows:
        wire(s, [(300, y), (760, y)], what, (330, y - 5), dash=(pin == "GDO2"))
    # decoupling right at the module: 100 nF + 10 µF between VCC and GND
    for x, label in ((660, "100 нФ"), (710, "10 мкФ")):
        wire(s, [(x, 260), (x, 278)])
        wire(s, [(x, 282), (x, 300)])
        s.add(capacitor(s, x, 280) + s.text(x, 316, label, 9))
    s.add(s.text(685, 332, "у самого VCC модуля", 8.5))
    wire(s, [(980, 280), (1080, 280), (1080, 120)], width=1.6)
    s.add(f'<path d="M1066,120 L1080,100 L1094,120" fill="none" stroke="{s.fg}" stroke-width="1.6"/>')
    s.add(s.text(1100, 150, "антенна ¼λ — штырь 17,3 см", 10, "start", "bold") + s.text(1100, 166, "(или спираль на 433 МГц),", 9, "start")
          + s.text(1100, 180, "вертикально, вне металлического щита", 9, "start"))
    s.add(s.text(1100, 380, "MQTT: home/devices/<имя шлюза>/…", 10, "start", "bold")
          + s.text(1100, 396, "sensors — показания привязанных датчиков", 9, "start")
          + s.text(1100, 410, "(tmp, hmt, bat); rf_debug — сырые пакеты", 9, "start")
          + s.text(1100, 424, "для отладки; cmd / ack — настройки с сервера", 9, "start"))
    return finish(s, "RF-шлюз беспроводных датчиков", "6", [
        "CC1101 питается только от 3,3 В платы ESP32 (5 В его сожгут); провода SPI — короткие, ≤ 10 см; общий GND.",
        "Шлюз — отдельное устройство (поз. 53), ставится там, где лучше приём от датчиков дома и улицы, не в металлическом щите котельной.",
        "Датчики привязываются с сервера: scan_sensors показывает всё, что слышно (модель, id, канал, RSSI), имя задаётся в админке.",
        "Wi‑Fi и брокер (192.168.55.10:1883) — через Wi‑Fi-портал шлюза, как у контроллера."])


def main() -> None:
    (HERE / "07a-structure.svg").write_text(render_structure(), encoding="utf-8")
    (HERE / "07b-sensors.svg").write_text(render_sensors(), encoding="utf-8")
    (HERE / "07c-boiler-opentherm.svg").write_text(render_boiler(), encoding="utf-8")
    (HERE / "07d-rf-gateway.svg").write_text(render_rf_gateway(), encoding="utf-8")


if __name__ == "__main__":
    main()
