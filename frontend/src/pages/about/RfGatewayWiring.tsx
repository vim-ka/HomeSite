/**
 * Pictorial wiring diagram of the RF gateway (A4): ESP32-DevKit (A4.1) + CC1101 433.92 MHz receiver (A4.2) on VSPI,
 * powered by a USB 5 V adapter.
 *
 * Source of truth: firmware/esp32-rf-gateway/PINOUT.md and docs/boiler-room sheet 6 (07d-rf-gateway.svg).
 */

import { Board, InfoBox, InlineCap, Legend, Tag, Title, Wire, XL, XR, rowY, theme, type Theme } from "./wiringParts";

const PAD_X = 1200;
/** CC1101 header top to bottom (module drawn with GDO2 on top so the SPI wires hardly cross). */
const CC_PINS: [string, number][] = [
  ["GDO2", 380], ["MISO", 410], ["MOSI", 440], ["SCK", 470], ["CSN", 500], ["GDO0", 530], ["VCC", 560], ["GND", 590],
];
const ccY = (name: string) => CC_PINS.find(([n]) => n === name)![1];

/** Signal wires: board pin → jog x → CC1101 pad. */
const SIGNALS: { pin: string; cc: string; color: string; jog: number | null; what: string }[] = [
  { pin: "IO19", cc: "MISO", color: "#22c55e", jog: 1000, what: "MISO" },
  { pin: "IO23", cc: "MOSI", color: "#3b82f6", jog: 1040, what: "MOSI" },
  { pin: "IO18", cc: "SCK", color: "#eab308", jog: null, what: "SCK" },
  { pin: "IO5", cc: "CSN", color: "#ec4899", jog: null, what: "CSN" },
  { pin: "IO4", cc: "GDO0", color: "#8b5cf6", jog: 1070, what: "данные" },
];

function Cc1101({ t }: { t: Theme }) {
  return (
    <g>
      <text x={1252} y={345} textAnchor="middle" fontSize="12" fontWeight="bold" fill={t.text}>A4.2 · CC1101 433 МГц</text>
      <rect x={1190} y={356} width={170} height={252} rx={6} fill="#047857" stroke="#064e3b" strokeWidth="1.5" />
      {CC_PINS.map(([name, y]) => (
        <g key={name}>
          <rect x={PAD_X - 6} y={y - 6} width={12} height={12} fill="#111827" />
          <circle cx={PAD_X} cy={y} r={3.5} fill="#d4a017" />
          <text x={PAD_X + 12} y={y + 3.5} fontSize="9" fill="#d1fae5">{name}</text>
        </g>
      ))}
      <rect x={1270} y={440} width={56} height={56} rx={2} fill="#111827" />
      <text x={1298} y={472} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#e5e7eb">CC1101</text>
      <rect x={1282} y={515} width={32} height={14} rx={6} fill="#d1d5db" stroke="#6b7280" />
      <text x={1298} y={545} textAnchor="middle" fontSize="7" fill="#d1fae5">26 МГц</text>
      {/* antenna pad and the quarter-wave whip */}
      <circle cx={1340} cy={372} r={5} fill="#d4a017" />
      <path d="M1340,372 V160" stroke="#cbd5e1" strokeWidth="3" strokeLinecap="round" />
      <circle cx={1340} cy={160} r={4} fill="#cbd5e1" />
      <text x={1328} y={200} textAnchor="end" fontSize="11" fontWeight="bold" fill={t.text}>антенна ¼λ — 17,3 см</text>
      <text x={1328} y={216} textAnchor="end" fontSize="9.5" fill={t.muted}>(или спираль на 433 МГц),</text>
      <text x={1328} y={230} textAnchor="end" fontSize="9.5" fill={t.muted}>вертикально, вне металла</text>
    </g>
  );
}

export default function RfGatewayWiring({ isDark, className }: { isDark: boolean; className?: string }) {
  const t = theme(isDark);
  return (
    <svg viewBox="0 0 1500 1000" className={className} role="img" aria-label="Схема подключения RF-шлюза">
      <rect width="1500" height="1000" rx="12" fill={t.bg} />
      <Title t={t} title="RF-шлюз — схема подключения" sub="A4: ESP32-DevKit + CC1101 433,92 МГц · прошивка esp32-rf-gateway"
        source="по firmware/esp32-rf-gateway/PINOUT.md и листу 6 документации котельной" />

      <Board t={t} designator="A4.1" name="ESP32-DevKit" />

      {/* power: USB 5 V adapter into the board's USB socket */}
      <path d="M760,834 V880" stroke="#374151" strokeWidth="7" strokeLinecap="round" />
      <rect x={690} y={880} width={140} height={60} rx={8} fill="#e5e7eb" stroke="#6b7280" />
      <text x={760} y={906} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#1f2937">USB 5 В, ≥ 1 А</text>
      <text x={760} y={922} textAnchor="middle" fontSize="9" fill="#475569">блок питания в розетку</text>
      <Wire d={`M${XL},${rowY("3V3", "L")} H624`} color="#f97316" />
      <Tag x={576} y={rowY("3V3", "L")} net="+3V3" t={t} />
      <Wire d={`M${XR},${rowY("GND", "R")} H896`} color={t.gnd} />
      <Tag x={896} y={rowY("GND", "R")} net="GND" t={t} />

      {/* SPI + data to CC1101 */}
      {SIGNALS.map((s) => {
        const ys = rowY(s.pin, "R");
        const yt = ccY(s.cc);
        const d = s.jog === null ? `M${XR},${ys} H${PAD_X}` : `M${XR},${ys} H${s.jog} V${yt} H${PAD_X}`;
        return <Wire key={s.pin} d={d} color={s.color} />;
      })}
      {SIGNALS.map((s) => (
        <text key={`l${s.pin}`} x={1150} y={ccY(s.cc) - 6} textAnchor="middle" fontSize="9" fontWeight="bold" fill={s.color}>{s.what}</text>
      ))}
      <Cc1101 t={t} />
      <text x={PAD_X - 12} y={ccY("GDO2") + 4} textAnchor="end" fontSize="9" fill={t.muted}>не подключать</text>
      <Wire d={`M${PAD_X},${ccY("VCC")} H1128`} color="#f97316" w={3} />
      <Tag x={1082} y={ccY("VCC")} net="+3V3" t={t} />
      <Wire d={`M${PAD_X},${ccY("GND")} H1128`} color={t.gnd} w={3} />
      <Tag x={1082} y={ccY("GND")} net="GND" t={t} />
      <InlineCap x={1148} y1={ccY("VCC")} y2={ccY("GND")} electrolytic t={t} />
      <InlineCap x={1174} y1={ccY("VCC")} y2={ccY("GND")} electrolytic={false} t={t} />
      <text x={1161} y={622} textAnchor="middle" fontSize="9.5" fontWeight="bold" fill={t.text}>C1 10 мкФ · C2 100 нФ</text>
      <text x={1161} y={635} textAnchor="middle" fontSize="9" fill={t.muted}>прямо на выводах VCC–GND модуля</text>

      <InfoBox x={40} y={150} w={520} t={t} title="Что принимает" lines={[
        "датчики 433 МГц: комнаты, улица, гараж, анализатор газа",
        "rtl_433_ESP — декодеры, OOK; GDO0 даёт поток бит на прерывание",
        "привязка с сервера: scan_sensors показывает всё, что слышно",
        "(модель, id, канал, RSSI), имя датчику даётся в админке",
        "MQTT: home/devices/<имя шлюза>/sensors, rf_debug, cmd / ack",
      ]} />
      <InfoBox x={40} y={330} w={520} t={t} title="Где ставить" lines={[
        "отдельное устройство, не в металлическом щите котельной —",
        "там, где лучше приём от датчиков дома и улицы",
        "Wi‑Fi и брокер — через портал шлюза, как у контроллера",
      ]} />

      <Legend x={24} y={790} w={540} t={t} nets={[
        ["+5V", "USB-блок питания в разъём платы (вывод 5V не нужен)"],
        ["+3V3", "со стабилизатора платы: CC1101 — только 3,3 В, 5 В его сожгут"],
        ["GND", "общий минус"],
      ]} notes={[
        "• Провода SPI — короткие, до 10 см.",
        "• Порядок выводов CC1101 у продавцов разный — сверять с надписями на плате.",
        "• IO5 (CSN) — загрузочный вывод, но CC1101 его вниз не тянет — загрузке не мешает.",
        "• Кнопка BOOT 5 с — сброс настроек Wi‑Fi. Строгая схема — лист 6.",
      ]} />
    </svg>
  );
}
