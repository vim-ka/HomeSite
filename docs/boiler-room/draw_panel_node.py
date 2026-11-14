"""Mains meter node in the house panel (sheet 9): ESP32 + PZEM-004T with a clamp, 18650 backup, Wi-Fi → MQTT.

Usage: python3 docs/boiler-room/draw_panel_node.py   → writes 07g-panel-node.svg

The node lives in the house panel, not in the boiler room: A8 measures the house input (voltage, current, power, kWh),
A7 reports over Wi-Fi straight to the MQTT broker. A9 + GB1 keep A7 running when the grid drops, so it reports
«нет сети» itself (VIN_OK falls) instead of just going silent.
"""

from pathlib import Path

from draw_schematic import SYM, Sch, devkit, frame

HERE = Path(__file__).resolve().parent

PANEL_NETS = {
    "3V3": "+3V3", "5V": "+5V", "GND": "GND",
    "IO17": "PZEM_TX", "IO16": "PZEM_RX",       # UART2: ESP TX → PZEM RX, PZEM TX → ESP RX
    "IO34": "VIN_OK", "IO35": "VBAT",           # ADC1 only: ADC2 is dead while Wi-Fi runs
}
PANEL_NOTES = {"EN": "кнопка EN на плате", "IO0": "кнопка BOOT на плате", "IO2": "светодиод платы",
               "TXD0": "USB платы", "RXD0": "USB платы"}
# net → (input voltage, top resistor, bottom resistor), kΩ
DIVIDERS = {"VIN_OK": (5.0, 22, 33), "VBAT": (4.2, 100, 100)}


def box(s: Sch, ref, pos, x, y, w, h, title, sub="") -> None:
    s.part(ref, f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffe0" stroke="{SYM}" stroke-width="2"/>'
                + Sch.t(x + w / 2, y - 8, title, 11, "middle", SYM, "bold")
                + (Sch.t(x + w / 2, y + h + 14, sub, 9, "middle") if sub else ""), pos)


def pin(s: Sch, x, y, name, left=True) -> None:
    s.add(Sch.t(x + 6 if left else x - 6, y + 4, name, 9.5, "start" if left else "end", SYM))


def divider(s: Sch, y, src, net, refs, pos=86) -> None:
    v_in, r_top, r_bottom = DIVIDERS[net]
    rt, rb, c = refs
    s.label(120, y, src, right=False)
    s.wire((120, y), (185, y))
    s.part(rt, s.resistor(200, y, False, rt, f"{r_top} кОм"), pos)
    s.wire((215, y), (420, y))
    s.label(420, y, net, right=True)
    for x, part in ((260, rb), (330, c)):
        s.dot(x, y)
        s.wire((x, y), (x, y + 20))
    s.part(rb, s.resistor(260, y + 35, True, rb, f"{r_bottom} кОм"), pos)
    s.wire((260, y + 50), (260, y + 62)); s.gnd(260, y + 62)
    s.wire((330, y + 20), (330, y + 32))
    s.part(c, s.capacitor(330, y + 40, c, "100 нФ"), pos)
    s.wire((330, y + 48), (330, y + 62)); s.gnd(330, y + 62)
    out = v_in * r_bottom / (r_top + r_bottom)
    s.add(Sch.t(520, y + 4, f"{src} {v_in:g} В → {out:.1f} В".replace(".", ","), 9.5))


def render_panel_node() -> str:
    s = Sch()
    s.add(Sch.t(40, 60, "Силовая часть 230 В — в щитке дома", 12, weight="bold"))
    # input: L and N after the house main breaker
    lx, nx = 80, 120
    s.add(Sch.t(lx, 100, "L", 10, "middle", SYM, "bold") + Sch.t(nx, 100, "N", 10, "middle", SYM, "bold")
          + Sch.t(150, 100, "от вводного автомата дома → к нагрузкам", 9.5))
    s.wire((lx, 108), (lx, 470))
    s.wire((nx, 108), (nx, 470))
    # TA1: split-core clamp on the input phase conductor
    s.part("TA1", f'<ellipse cx="{lx}" cy="150" rx="16" ry="7" fill="none" stroke="{SYM}" stroke-width="2"/>'
                  + Sch.t(lx - 22, 146, "TA1", 10, "end", SYM, "bold") + Sch.t(lx - 22, 160, "100 А", 9, "end"), 83)
    s.wire((lx + 16, 147), (480, 147))
    s.wire((lx + 16, 153), (300, 153), (300, 177), (480, 177))
    # QF7 → FU1 → A8 voltage input; QF7 → G3
    s.dot(lx, 230)
    s.wire((lx, 230), (150, 230))
    s.part("QF7", f'<rect x="150" y="222" width="50" height="16" fill="#fffff0" stroke="{SYM}"/>'
                  + Sch.t(175, 216, "QF7 C2", 9, "middle", SYM, "bold"), 85)
    s.wire((200, 230), (280, 230))
    s.dot(250, 230)
    s.part("FU1", f'<rect x="280" y="224" width="40" height="12" fill="#fffff0" stroke="{SYM}"/>'
                  + Sch.t(300, 218, "FU1 1 А", 9, "middle", SYM, "bold"), 85)
    s.wire((320, 230), (480, 230))
    s.dot(nx, 260)
    s.wire((nx, 260), (480, 260))
    box(s, "A8", 83, 480, 130, 220, 150, "A8  PZEM-004T v3.0, 100 А", "Modbus RTU 9600, опторазвязка")
    for y, name in ((147, "CT+"), (177, "CT−"), (230, "L"), (260, "N")):
        pin(s, 480, y, name)
    for y, name in ((160, "5V"), (190, "RX"), (220, "TX"), (250, "GND")):
        pin(s, 700, y, name, left=False)
    s.wire((700, 160), (740, 160)); s.vcc(740, 160, "+3V3")
    s.wire((700, 190), (740, 190)); s.label(740, 190, "PZEM_TX", right=True)
    s.wire((700, 220), (740, 220)); s.label(740, 220, "PZEM_RX", right=True)
    s.wire((700, 250), (740, 250)); s.gnd(740, 250)
    s.add(Sch.t(720, 290, "TTL-сторона A8 — от +3V3: уровни ESP32", 9)
          + Sch.t(720, 304, "+3V3 — вывод 3V3 платы A7 (её стабилизатор 5 → 3,3 В)", 9))
    # G3 5 V supply
    s.wire((250, 230), (250, 400), (480, 400))
    s.dot(nx, 430)
    s.wire((nx, 430), (480, 430))
    box(s, "G3", 84, 480, 380, 220, 70, "G3  БП 5 В, 2 А на DIN")
    pin(s, 480, 400, "L"); pin(s, 480, 430, "N")
    pin(s, 700, 400, "+5V", left=False); pin(s, 700, 430, "−", left=False)
    s.wire((700, 400), (820, 400))
    s.dot(760, 400); s.wire((760, 400), (760, 365)); s.label(760, 365, "5V_IN", right=True)
    s.wire((700, 430), (740, 430)); s.gnd(740, 430)
    # A9 charger + boost with pass-through, GB1 18650
    box(s, "A9", 84, 820, 380, 180, 90, "A9  модуль ИБП 5 В на 18650")
    pin(s, 820, 400, "IN 5V"); pin(s, 820, 440, "GND")
    pin(s, 1000, 400, "OUT 5V", left=False); pin(s, 1000, 440, "GND", left=False)
    s.add(Sch.t(845, 465, "BAT+", 9, fill=SYM) + Sch.t(975, 465, "BAT−", 9, "end", SYM))
    s.wire((820, 440), (800, 440)); s.gnd(800, 440)
    s.wire((1000, 400), (1040, 400)); s.vcc(1040, 400, "+5V")
    s.wire((1000, 440), (1030, 440)); s.gnd(1030, 440)
    s.wire((860, 470), (860, 540), (900, 540))
    s.wire((912, 540), (960, 540), (960, 470))
    s.part("GB1", f'<path d="M900,526 V554 M912,533 V547" stroke="{SYM}" stroke-width="2.5"/>'
                  + Sch.t(894, 528, "+", 10, "end", SYM)
                  + Sch.t(906, 575, "GB1  18650, 3,7 В, ≥ 2500 мА·ч", 9.5, "middle", SYM, "bold"), 84)
    s.dot(860, 505); s.wire((860, 505), (800, 505)); s.label(800, 505, "BAT+", right=False)

    # dividers: grid present, battery voltage
    s.add(Sch.t(40, 640, "Контроль сети и батареи (АЦП1)", 12, weight="bold"))
    divider(s, 700, "5V_IN", "VIN_OK", ("R6", "R7", "C6"))
    divider(s, 840, "BAT+", "VBAT", ("R8", "R9", "C7"))

    # controller
    devkit(s, x0=1180, y0=190, nets=PANEL_NETS, notes=PANEL_NOTES, ref="A7", pos=82,
           title="A7  ESP32-DevKitC-32U (внешняя антенна)", sub="прошивка esp32-panel-meter · Wi‑Fi → MQTT")
    s.add(Sch.t(1310, 820, "антенна 2,4 ГГц на кабеле IPEX —", 9.5, "middle")
          + Sch.t(1310, 834, "вывести за металлический корпус щита", 9.5, "middle"))
    return frame(s, "Узел учёта сети в щитке дома: схема принципиальная", "9", [
        "A8 меряет ввод дома (однофазный): TA1 — на фазный провод после вводного автомата, стрелкой к нагрузке; напряжение — через QF7 и FU1.",
        "Питание: QF7 → G3 5 В → A9 (заряд 18650 + повышающий 5 В со сквозным питанием, не отключается при малой нагрузке) → A7 5V.",
        "Сеть пропала: G3 молчит, VIN_OK → 0 (≈ 3,0 В при сети), A8 не отвечает — A7 от GB1 шлёт «нет сети». VBAT = BAT+ / 2. Только ADC1: ADC2 не работает при Wi‑Fi.",
        "MQTT: home/devices/{имя}/heartbeat — mains_v, mains_hz, mains_a, mains_w, mains_kwh, mains_ok, vbat. Позиции 82–86 спецификации."])


def main() -> None:
    (HERE / "07g-panel-node.svg").write_text(render_panel_node(), encoding="utf-8")


if __name__ == "__main__":
    main()
