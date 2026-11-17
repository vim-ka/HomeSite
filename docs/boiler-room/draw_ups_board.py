"""Boiler room UPS board (sheet 11): ESP32 + MAX3232 reads the UPS over its COM port (APC «Smart»), Wi-Fi → MQTT.

Usage: python3 docs/boiler-room/draw_ups_board.py   → writes 07i-ups-board.svg

A9 sits in the boiler room panel on a DIN holder (rail 4, sheet 10) and is fed by the panel's 5 V supply G1 — the
panel itself runs from the UPS, so the board keeps reporting during an outage. A10 converts the UART levels to
RS-232; W1 is a three-wire cable wired like APC 940-0024C. Source: docs/superpowers/specs/2026-11-14-ups-monitoring-design.md.
"""

from pathlib import Path

from draw_schematic import SYM, Sch, devkit, frame

HERE = Path(__file__).resolve().parent

UPS_NETS = {
    "3V3": "+3V3", "5V": "+5V", "GND": "GND",
    "IO17": "UPS_TX", "IO16": "UPS_RX",          # UART2: ESP TX → A10 T1IN, A10 R1OUT → ESP RX
}
UPS_NOTES = {"EN": "кнопка EN на плате", "IO0": "кнопка BOOT на плате", "IO2": "светодиод платы",
             "TXD0": "USB платы", "RXD0": "USB платы"}
# W1: (A10 RS-232 side, UPS DB9 contact, what the UPS contact is) — as APC cable 940-0024C
CABLE = [("T1OUT", 1, "RxD ИБП"), ("R1IN", 2, "TxD ИБП"), ("GND", 4, "GND")]


def box(s: Sch, ref, pos, x, y, w, h, title, sub="") -> None:
    s.part(ref, f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffe0" stroke="{SYM}" stroke-width="2"/>'
                + Sch.t(x + w / 2, y - 8, title, 11, "middle", SYM, "bold")
                + (Sch.t(x + w / 2, y + h + 14, sub, 9, "middle") if sub else ""), pos)


def pin(s: Sch, x, y, name, left=True) -> None:
    s.add(Sch.t(x + 6 if left else x - 6, y + 4, name, 9.5, "start" if left else "end", SYM))


def render_ups_board() -> str:
    s = Sch()
    # the UPS itself: existing equipment, not a specification position
    s.add(f'<rect x="60" y="120" width="170" height="160" fill="none" stroke="{SYM}" stroke-width="2" stroke-dasharray="6 4"/>'
          + Sch.t(145, 112, "ИБП котельной (есть)", 11, "middle", SYM, "bold")
          + Sch.t(145, 296, "Smart-UPS 750, COM-порт DB9", 9, "middle")
          + Sch.t(145, 310, "протокол APC «Smart», 2400 8N1", 9, "middle"))
    a10_left, a10_right = 560, 780
    for i, (a10_pin, contact, what) in enumerate(CABLE):
        y = 160 + i * 40
        pin(s, 230, y, f"{contact}  {what}", left=False)
        s.wire((230, y), (a10_left, y))
    s.part("W1", Sch.t(395, 146, "W1  кабель RS-232, 3 провода", 10, "middle", SYM, "bold")
                 + Sch.t(395, 268, "DB9 к ИБП — DB9 к A10, распайка как APC 940-0024C", 9, "middle"), 90)
    box(s, "A10", 89, a10_left, 130, a10_right - a10_left, 150, "A10  модуль RS-232 ↔ TTL (MAX3232)", "питание 3,3 В — уровни ESP32")
    for i, (a10_pin, *_) in enumerate(CABLE):
        pin(s, a10_left, 160 + i * 40, a10_pin + (" (DB9-5)" if a10_pin == "GND" else ""))
    for y, name in ((150, "VCC"), (180, "TXD (T1IN)"), (210, "RXD (R1OUT)"), (250, "GND")):
        pin(s, a10_right, y, name, left=False)
    s.wire((a10_right, 150), (a10_right + 40, 150)); s.vcc(a10_right + 40, 150, "+3V3")
    s.wire((a10_right, 180), (a10_right + 40, 180)); s.label(a10_right + 40, 180, "UPS_TX", right=True)
    s.wire((a10_right, 210), (a10_right + 40, 210)); s.label(a10_right + 40, 210, "UPS_RX", right=True)
    s.wire((a10_right, 250), (a10_right + 40, 250)); s.gnd(a10_right + 40, 250)
    # G1: the panel's 5 V supply
    box(s, "G1", 54, a10_left, 420, a10_right - a10_left, 70, "G1  БП 5 В щита котельной (HDR-30-5)",
        "щит питается от ИБП — плата работает и без сети")
    pin(s, a10_left, 440, "L"); pin(s, a10_left, 470, "N")
    s.wire((a10_left, 440), (a10_left - 60, 440)); s.wire((a10_left, 470), (a10_left - 60, 470))
    s.add(Sch.t(a10_left - 66, 444, "L′", 10, "end", SYM, "bold") + Sch.t(a10_left - 66, 474, "N", 10, "end", SYM, "bold")
          + Sch.t(a10_left - 66, 500, "от щита (лист 3)", 9, "end"))
    pin(s, a10_right, 440, "+V", left=False); pin(s, a10_right, 470, "−V", left=False)
    s.wire((a10_right, 440), (a10_right + 60, 440)); s.vcc(a10_right + 60, 440, "+5V")
    s.wire((a10_right, 470), (a10_right + 40, 470)); s.gnd(a10_right + 40, 470)
    s.add(Sch.t(670, 530, "+5V — отдельным проводом от клемм G1 на вывод 5V платы A9", 9, "middle"))
    # the board
    devkit(s, x0=1180, y0=190, nets=UPS_NETS, notes=UPS_NOTES, ref="A9", pos=88,
           title="A9  ESP32-DevKitC (WROOM-32)", sub="прошивка esp32-ups · Wi‑Fi → MQTT")
    s.add(Sch.t(1310, 820, "в щите на DIN-держателе (рейка 4, лист 10);", 9.5, "middle")
          + Sch.t(1310, 834, "антенна платы — к дверце, подальше от металла", 9.5, "middle"))
    return frame(s, "Плата ИБП котельной: схема принципиальная", "11", [
        "A9 читает ИБП по COM-порту через A10 (APC «Smart», 2400 8N1, UART2: IO17 → T1IN, R1OUT → IO16) и только читает — ничем не управляет.",
        "W1 — только 3 провода (1, 2, 4 на стороне ИБП); обычный COM-кабель не годится — может выключить ИБП. Распайку сверить по документации APC.",
        "Питание: G1 → A9 5V; A10 — от +3V3 A9. USB и 5 В от G1 — не одновременно. MQTT: home/devices/{имя}/ups. Позиции 54, 88–90."])


def main() -> None:
    (HERE / "07i-ups-board.svg").write_text(render_ups_board(), encoding="utf-8")


if __name__ == "__main__":
    main()
