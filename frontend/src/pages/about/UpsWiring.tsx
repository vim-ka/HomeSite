/**
 * Pictorial wiring diagram of the boiler room UPS board: ESP32-DevKitC reads the Smart-UPS over its COM port
 * (APC «Smart» protocol) through a MAX3232 RS-232 ↔ TTL module and publishes the state to MQTT.
 *
 * Source of truth: docs/superpowers/specs/2026-11-14-ups-monitoring-design.md (section «Источник ESP32 по MQTT»)
 * and the plan's firmware task (UART2: RX = GPIO16, TX = GPIO17). Cable pinout as APC 940-0024C.
 */

import { Board, Db9, InfoBox, Legend, Tag, Title, Wire, XL, XR, rowY, theme, type Theme } from "./wiringParts";

const TX = "#f97316";
const RX = "#22c55e";

/** MAX3232 RS-232 ↔ TTL module: TTL header on the left edge (pads at x = 1000), DB9 female on the right. */
function Max3232({ t }: { t: Theme }) {
  const pads: [string, number][] = [["VCC", 500], ["TXD", 530], ["RXD", 560], ["GND", 590]];
  return (
    <g>
      <text x={1085} y={468} textAnchor="middle" fontSize="12" fontWeight="bold" fill={t.text}>A10 · модуль RS-232 ↔ TTL</text>
      <rect x={990} y={478} width={180} height={134} rx={6} fill="#1d4ed8" stroke="#1e3a8a" strokeWidth="1.5" />
      {pads.map(([name, y]) => (
        <g key={name}>
          <rect x={994} y={y - 6} width={12} height={12} fill="#111827" />
          <circle cx={1000} cy={y} r={3.5} fill="#d4a017" />
          <text x={1012} y={y + 3.5} fontSize="9" fill="#dbeafe">{name}</text>
        </g>
      ))}
      <rect x={1060} y={522} width={50} height={46} rx={2} fill="#111827" />
      <text x={1085} y={542} textAnchor="middle" fontSize="8" fontWeight="bold" fill="#e5e7eb">MAX</text>
      <text x={1085} y={553} textAnchor="middle" fontSize="8" fontWeight="bold" fill="#e5e7eb">3232</text>
      {([[1066, 500], [1092, 500], [1066, 590], [1092, 590]] as const).map(([x, y]) => (
        <rect key={`${x}${y}`} x={x} y={y - 5} width={14} height={9} rx={1} fill="#f59e0b" />
      ))}
      <text x={1085} y={628} textAnchor="middle" fontSize="9" fill={t.muted}>питание 3,3 В · 4 конденсатора 0,1 мкФ на плате</text>
    </g>
  );
}

/** Smart-UPS rear panel with the COM port (DB9) and the IEC outlets. */
function SmartUps({ t }: { t: Theme }) {
  return (
    <g>
      <rect x={1290} y={430} width={180} height={270} rx={8} fill="#1f2937" stroke="#4b5563" strokeWidth="1.5" />
      <text x={1380} y={456} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#e5e7eb">Smart-UPS 750</text>
      <text x={1380} y={472} textAnchor="middle" fontSize="9" fill="#9ca3af">задняя панель</text>
      <text x={1336} y={500} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#e5e7eb">COM</text>
      {[0, 1, 2, 3].map((i) => (
        <g key={i}>
          <rect x={1385 + (i % 2) * 42} y={520 + Math.floor(i / 2) * 50} width={32} height={36} rx={3} fill="#111827" stroke="#6b7280" />
          <rect x={1393 + (i % 2) * 42} y={530 + Math.floor(i / 2) * 50} width={6} height={10} fill="#374151" />
          <rect x={1409 + (i % 2) * 42} y={530 + Math.floor(i / 2) * 50} width={6} height={10} fill="#374151" />
        </g>
      ))}
      <text x={1427} y={640} textAnchor="middle" fontSize="9" fill="#9ca3af">выходы → щит</text>
      <rect x={1330} y={660} width={100} height={26} rx={3} fill="#111827" stroke="#6b7280" />
      <text x={1380} y={677} textAnchor="middle" fontSize="9" fill="#9ca3af">вход 230 В</text>
      <text x={1380} y={722} textAnchor="middle" fontSize="10" fill={t.muted}>питает весь щит котельной</text>
    </g>
  );
}

/** The panel's 5 V PSU G1 with its output terminals (+V at y 630, −V at y 670). */
function PanelPsu({ t }: { t: Theme }) {
  return (
    <g>
      <rect x={180} y={600} width={250} height={100} rx={6} fill="#94a3b8" stroke="#475569" strokeWidth="1.5" />
      <text x={290} y={642} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#1f2937">G1 · MeanWell HDR-30-5</text>
      <text x={290} y={660} textAnchor="middle" fontSize="9.5" fill="#334155">БП щита котельной, 5 В</text>
      {[["+V", 630], ["−V", 670]].map(([n, y]) => (
        <g key={n as string}>
          <rect x={410} y={(y as number) - 9} width={20} height={18} rx={2} fill="#e5e7eb" stroke="#475569" />
          <text x={420} y={(y as number) + 4} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#1f2937">{n}</text>
        </g>
      ))}
      <text x={180} y={590} fontSize="9.5" fill={t.muted}>щит питается от ИБП — плата работает и без света</text>
    </g>
  );
}

export default function UpsWiring({ isDark, className }: { isDark: boolean; className?: string }) {
  const t = theme(isDark);
  return (
    <svg viewBox="0 0 1500 1000" className={className} role="img" aria-label="Схема подключения платы ИБП котельной">
      <rect width="1500" height="1000" rx="12" fill={t.bg} />
      <Title t={t} title="Плата ИБП котельной — схема подключения"
        sub="ESP32-DevKitC · MAX3232 · Smart-UPS по COM-порту (APC «Smart»)"
        source="по листу 11 документации котельной и спеке мониторинга ИБП" />

      <Board t={t} designator="A9" name="ESP32-DevKitC · плата ИБП" antenna="антенна — к дверце щита, подальше от металла" />

      {/* power: G1 +V → 5V pin; −V → GND */}
      <PanelPsu t={t} />
      <Wire d={`M430,630 H578 V${rowY("5V", "L")} H${XL}`} color="#dc2626" />
      <Wire d="M430,670 H470" color={t.gnd} />
      <Tag x={470} y={670} net="GND" t={t} />
      <Wire d={`M${XL},${rowY("3V3", "L")} H624`} color="#f97316" />
      <Tag x={576} y={rowY("3V3", "L")} net="+3V3" t={t} />
      <Wire d={`M${XR},${rowY("GND", "R")} H896`} color={t.gnd} />
      <Tag x={896} y={rowY("GND", "R")} net="GND" t={t} />

      {/* UART2 → MAX3232 TTL side */}
      <Max3232 t={t} />
      <Wire d={`M${XR},${rowY("IO17", "R")} H1000`} color={TX} />
      <Wire d={`M${XR},${rowY("IO16", "R")} H1000`} color={RX} />
      <text x={935} y={rowY("IO17", "R") - 7} textAnchor="middle" fontSize="9" fontWeight="bold" fill={TX}>TX2 →</text>
      <text x={935} y={rowY("IO16", "R") + 16} textAnchor="middle" fontSize="9" fontWeight="bold" fill={RX}>← RX2</text>
      <Wire d="M1000,500 H976" color="#f97316" w={3} />
      <Tag x={930} y={500} net="+3V3" t={t} />
      <Wire d="M1000,590 H976" color={t.gnd} w={3} />
      <Tag x={930} y={590} net="GND" t={t} />

      {/* RS-232 cable to the UPS */}
      <Db9 x={1166} y={545} label="" male={false} t={t} />
      <SmartUps t={t} />
      <path d="M1194,545 C1240,545 1250,545 1306,545" fill="none" stroke="#475569" strokeWidth="9" strokeLinecap="round" />
      <path d="M1194,545 C1240,545 1250,545 1306,545" fill="none" stroke="#94a3b8" strokeWidth="5" strokeLinecap="round" />
      <Db9 x={1306} y={545} label="" male t={t} />
      <text x={1248} y={526} textAnchor="middle" fontSize="8.5" fontWeight="bold" fill={t.text}>W1</text>
      <text x={1248} y={568} textAnchor="middle" fontSize="8.5" fill={t.muted}>3 провода</text>

      {/* protocol */}
      <InfoBox x={950} y={150} w={520} t={t} title="Протокол APC «Smart» по RS-232" lines={[
        "UART2: IO16 = RX, IO17 = TX · 2400 бод, 8N1",
        "«Y» → ответ «SM» (smart-режим), потом опрос раз в 60 с:",
        "L сеть · O выход · f заряд · j время · P нагрузка · B батарея · Q флаги · X самотест",
        "MQTT: home/devices/<имя>/ups — JSON, не retained",
        "сеть ↔ батарея — публикует сразу, не дожидаясь минуты",
        "только читает ИБП, ничем не управляет",
      ]} />

      {/* cable pinout */}
      <InfoBox x={950} y={760} w={520} t={t} accent="#f97316" title="Кабель плата → ИБП (распайка как у APC 940-0024C)" lines={[
        "передача (T1OUT) модуля    →  контакт 1 DB9 ИБП (приём ИБП)",
        "приём (R1IN) модуля           ←  контакт 2 DB9 ИБП (передача ИБП)",
        "GND (контакт 5 DB9 модуля)  —  контакт 4 DB9 ИБП (GND)",
        "остальные контакты ИБП — не подключать",
      ]} />

      <Legend x={24} y={760} w={530} t={t} nets={[
        ["+5V", "от БП G1 щита котельной → вывод 5V платы"],
        ["+3V3", "со стабилизатора платы: модуль MAX3232 (не 5 В — уровни ESP32)"],
        ["GND", "общий минус для всего"],
      ]} notes={[
        "• Обычный COM-кабель не годится: у APC свои контакты, он может выключить ИБП.",
        "• Какой контакт DB9 модуля — передача: в покое на нём −5…−6 В к GND (тестером).",
        "• ИБП молчит — поменять местами провода на контактах 1 и 2.",
        "• Питание платы — USB или 5 В от G1, не вместе: перед прошивкой снять 5 В.",
        "• Плата — в щите на DIN-держателе; распайку сверить по документации APC.",
      ]} />
    </svg>
  );
}
