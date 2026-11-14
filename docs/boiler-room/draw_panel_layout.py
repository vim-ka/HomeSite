"""Boiler room panel layout (sheet 10): DIN rails of a 72-module box (4 × 18) and the door with the panel indicators.

Usage: python3 docs/boiler-room/draw_panel_layout.py   → writes 07h-panel-layout.svg

Front view, widths in DIN modules (17.5 mm), heights not to scale. 230 V at the top (mains cables enter from above),
the low-voltage electronics on the bottom rail (sensor cables enter from below), the relay boards between them.
"""

from pathlib import Path

from draw_piping import Sheet
from draw_schematic import COLOUR, OUTPUTS
from draw_wiring import finish

HERE = Path(__file__).resolve().parent
ROW_MODULES = 18
MOD = 32                      # px per DIN module

# rail title, [(ref, spec position, modules, line 1, line 2)]; ref "" = reserve
ROWS = [
    ("Рейка 1 — ввод, защита, коммутация 230 В", [
        ("QF1", 60, 2, "QF1", "C32 ввод"), ("", None, 2, "резерв", "реле напр."),
        ("QF2", 60, 1, "QF2", "C6"), ("QF3", 60, 1, "QF3", "C6"), ("QF4", 60, 1, "QF4", "C10"),
        ("QF5", 60, 2, "QF5", "АВДТ ТЭН"), ("QF6", 60, 2, "QF6", "АВДТ скв."),
        ("KM1", 58, 1, "KM1", "ТЭН"), ("KM2", 65, 1, "KM2", "скв."),
        ("HL1", 59, 1, "HL1", "жёлт."), ("HL2", 59, 1, "HL2", "красн."), ("HA1", 59, 1, "HA1", "зумм.")]),
    ("Рейка 2 — питание 5 В и клеммы нагрузок", [
        ("G1", 54, 2, "G1", "5 В 3 А"), ("XT1", 63, 4, "XT1 — L", "14 нагрузок"),
        ("XT1", 63, 4, "XT1 — N", "14 нагрузок"), ("XT1", 63, 4, "XT1 — PE", "14 нагрузок"),
        ("", None, 4, "резерв", "")]),
    ("Рейка 3 — платы реле (катушки 5 В, контакты 230 В)", [
        ("A2.1", 51, 8, "A2.1 реле 8 кан.", "K0–K6, K15: котёл, насосы, контакторы"),
        ("A2.2", 51, 8, "A2.2 реле 8 кан.", "K7–K14: приводы YA1–YA3, ALARM"), ("", None, 2, "резерв", "")]),
    ("Рейка 4 — электроника 3,3 / 5 В", [
        ("A1", 50, 6, "A1 ESP32 + плата обвязки", "X1–X7, JP1, R, C (поз. 69)"), ("A3", 52, 2, "A3", "OpenTherm"),
        ("", None, 10, "резерв", "")]),
]

# door: (ref, panel label, colour); SA1 last
_BY_HL = {hl: (label, colour) for _, _, _, hl, label, colour in OUTPUTS if hl}
DOOR = [("HL3", "PB", "зелёный")] + [(f"HL{i}", *_BY_HL[f"HL{i}"]) for i in range(4, 16)] + [("SA1", "Авто / Ручной", "")]


def render_layout() -> str:
    s = Sheet("gost")
    fg = s.fg
    px, py, pitch, dev_h = 70, 95, 172, 104
    width = ROW_MODULES * MOD
    s.add(s.text(px - 20, 62, "Щит котельной 72 модуля (4 × 18), вид спереди без двери", 12, "start", "bold"))
    s.add(f'<rect x="{px - 30}" y="{py - 20}" width="{width + 60}" height="{4 * pitch + 10}" rx="6" fill="none" '
          f'stroke="{fg}" stroke-width="2"/>')
    s.add(s.text(px + width, py + 8, "↓ ввод 230 В и кабели нагрузок — сверху", 9.5, "end"))
    for r, (title, items) in enumerate(ROWS):
        top = py + r * pitch
        rail_y = top + 18 + dev_h / 2
        s.add(s.text(px, top + 8, title, 10, "start", "bold"))
        s.add(f'<rect x="{px - 10}" y="{rail_y - 9}" width="{width + 20}" height="18" fill="#e5e7eb" stroke="{fg}" stroke-width="0.8"/>')
        x = px
        for ref, pos, mods, l1, l2 in items:
            w = mods * MOD
            dash = ' stroke-dasharray="4 3"' if not ref else ""
            body = (f'<rect x="{x + 1}" y="{top + 18}" width="{w - 2}" height="{dev_h}" rx="3" fill="{s.bg}" '
                    f'stroke="{fg}" stroke-width="1.2"{dash}/>')
            cx = x + w / 2
            if mods == 1:
                body += (f'<text x="{cx + 3}" y="{top + 18 + dev_h / 2}" font-size="10" font-weight="bold" text-anchor="middle" '
                         f'fill="{fg}" transform="rotate(-90 {cx + 3} {top + 18 + dev_h / 2})">{l1} {l2}</text>')
            else:
                body += s.text(cx, top + 18 + dev_h / 2 - 4, l1, 10 if mods < 6 else 11, weight="bold")
                if l2:
                    body += s.text(cx, top + 18 + dev_h / 2 + 12, l2, 9)
            body += s.text(cx, top + 18 + dev_h + 13, str(mods), 8, fill="#666")
            if ref:
                s.item(pos, ref, body)
            else:
                s.add(body)
            x += w
    s.add(s.text(px + width / 2, py + 4 * pitch + 6, "↑ кабели датчиков, OpenTherm, шины 1-Wire — снизу", 9.5))

    # door
    dx, dy, dw, dh = 790, 75, 560, 560
    s.add(s.text(dx, 62, "Дверь щита (глухая), вид спереди", 12, "start", "bold"))
    s.add(f'<rect x="{dx}" y="{dy}" width="{dw}" height="{dh}" rx="6" fill="none" stroke="{fg}" stroke-width="2"/>')
    rows = [DOOR[0:7], DOOR[7:13]]
    for i, group in enumerate(rows):
        y = dy + 90 + i * 150
        s.add(s.text(dx + 20, y - 45, ("Работа: питание котла, насосы, нагрузки" if i == 0 else "Приводы: открыть (красный) / закрыть (синий)"), 10, "start", "bold"))
        step = (dw - 40) / len(group)
        for j, (ref, label, colour) in enumerate(group):
            cx = dx + 20 + step * (j + 0.5)
            body = (f'<circle cx="{cx}" cy="{y}" r="16" fill="{COLOUR.get(colour, "#fff")}" stroke="{fg}" stroke-width="1.5"/>'
                    + s.text(cx, y + 34, label, 10, weight="bold") + s.text(cx, y + 48, ref, 9))
            s.item(68, ref, body)
    ref, label, _ = DOOR[-1]
    cx, cy = dx + dw / 2, dy + 430
    body = (f'<circle cx="{cx}" cy="{cy}" r="26" fill="{s.bg}" stroke="{fg}" stroke-width="1.8"/>'
            f'<path d="M{cx},{cy - 20} V{cy + 20}" stroke="{fg}" stroke-width="5" stroke-linecap="round"/>'
            + s.text(cx - 50, cy + 4, "Авто", 10, "end", "bold") + s.text(cx + 50, cy + 4, "Ручной", 10, "start", "bold")
            + s.text(cx, cy + 46, "SA1 «Авто / Ручной»", 10, weight="bold"))
    s.item(66, ref, body)
    s.add(s.text(dx + dw / 2, dy + dh - 20, "индикаторы Ø22 мм, 230 В; провода к двери — гибким жгутом с петлёй у петель", 9))

    return finish(s, "Щит котельной: размещение на DIN-рейках", "10", [
        "Сверху вниз: 230 В (ввод, автоматы, контакторы) → клеммы и БП → платы реле → электроника 3,3/5 В. Силовые и сигнальные",
        "кабели — в разных кабель-каналах (по бокам щита), не в одном жгуте. Шины N и PE — штатные шины корпуса щита; цифра под устройством — ширина в модулях.",
        "Вне щита: ИБП G2 — рядом на полу/полке; сигнализатор газа A5 — на стене по паспорту; RF-шлюз A4 — вне металла; SK1 — на трубе, SK2 — в блоке ТЭНа.",
        "Занято 52 модуля из 72, свободно 20 (пунктир): 2 в рейке 1 — под реле напряжения на вводе, остальное — резерв."])


def main() -> None:
    (HERE / "07h-panel-layout.svg").write_text(render_layout(), encoding="utf-8")


if __name__ == "__main__":
    main()
