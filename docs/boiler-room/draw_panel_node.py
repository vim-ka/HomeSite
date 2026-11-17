"""Mains meter node in the house panel (sheet 9): ESP32 + PZEM-004T with a clamp, Wi-Fi → MQTT.

Usage: python3 docs/boiler-room/draw_panel_node.py   → writes 07g-panel-node.svg

The node lives in the house panel, not in the boiler room: A8 measures the house input (voltage, current, power, kWh),
A7 reports over Wi-Fi straight to the MQTT broker. No battery backup: the node goes dark with the grid, and the
outage itself is reported by the UPSes (UPS monitoring), not by this node.
"""

from pathlib import Path

from draw_schematic import SYM, Sch, devkit, frame

HERE = Path(__file__).resolve().parent

PANEL_NETS = {
    "3V3": "+3V3", "5V": "+5V", "GND": "GND",
    "IO17": "PZEM_TX", "IO16": "PZEM_RX",       # UART2: ESP TX → PZEM RX, PZEM TX → ESP RX
}
PANEL_NOTES = {"EN": "кнопка EN на плате", "IO0": "кнопка BOOT на плате", "IO2": "светодиод платы",
               "TXD0": "USB платы", "RXD0": "USB платы"}

def box(s: Sch, ref, pos, x, y, w, h, title, sub="") -> None:
    s.part(ref, f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffe0" stroke="{SYM}" stroke-width="2"/>'
                + Sch.t(x + w / 2, y - 8, title, 11, "middle", SYM, "bold")
                + (Sch.t(x + w / 2, y + h + 14, sub, 9, "middle") if sub else ""), pos)


def pin(s: Sch, x, y, name, left=True) -> None:
    s.add(Sch.t(x + 6 if left else x - 6, y + 4, name, 9.5, "start" if left else "end", SYM))


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
    s.wire((700, 400), (760, 400)); s.vcc(760, 400, "+5V")
    s.wire((700, 430), (740, 430)); s.gnd(740, 430)
    s.add(Sch.t(590, 480, "+5V — на вывод 5V платы A7; резерва нет: узел гаснет вместе с сетью", 9, "middle"))
    # controller
    devkit(s, x0=1180, y0=190, nets=PANEL_NETS, notes=PANEL_NOTES, ref="A7", pos=82,
           title="A7  ESP32-DevKitC-32U (внешняя антенна)", sub="прошивка esp32-panel-meter · Wi‑Fi → MQTT")
    s.add(Sch.t(1310, 820, "антенна 2,4 ГГц на кабеле IPEX —", 9.5, "middle")
          + Sch.t(1310, 834, "вывести за металлический корпус щита", 9.5, "middle"))
    return frame(s, "Узел учёта сети в щитке дома: схема принципиальная", "9", [
        "A8 меряет ввод дома (однофазный): TA1 — на фазный провод после вводного автомата, стрелкой к нагрузке; напряжение — через QF7 и FU1.",
        "Питание: QF7 → G3 5 В → A7 5V, без резерва. Сеть пропала — узел гаснет; «нет электричества» сообщают ИБП (мониторинг ИБП), не этот узел.",
        "MQTT: home/devices/{имя}/heartbeat — mains_v, mains_hz, mains_a, mains_w, mains_kwh, mains_pf. Позиции 82–85 спецификации."])


def main() -> None:
    (HERE / "07g-panel-node.svg").write_text(render_panel_node(), encoding="utf-8")


if __name__ == "__main__":
    main()
