/**
 * Pictorial wiring diagram of the mains meter node in the house panel (A7): ESP32-DevKitC-32U with an external
 * antenna reads a PZEM-004T v3.0 (A8) over UART2 (Modbus RTU); the split-core clamp TA1 sits on the input phase.
 *
 * Source of truth: docs/boiler-room sheet 9 (07g-panel-node.svg, draw_panel_node.py) and 07-wiring.md § 7.7.
 * No battery: the node goes dark with the grid, the outage is reported by the UPSes.
 */

import { Board, InfoBox, Legend, Tag, Title, Wire, XL, XR, rowY, theme, type Theme } from "./wiringParts";

const TX = "#f97316";
const RX = "#22c55e";
const L_COL = "#b45309";
const N_COL = "#2563eb";
const XLINE = 1400; // phase L, top to bottom
const XN = 1450;    // neutral N

/** Horizontal neutral tap from N to x = toX at y, hopping over the phase line. */
const nTap = (y: number, toX: number) => `M${XN},${y} H${XLINE + 7} a7,7 0 0 0 -14,0 H${toX}`;

/** PZEM-004T v3.0: TTL header on the left (x = 1000), mains / CT terminals on the right (x = 1250). */
function Pzem({ t }: { t: Theme }) {
  const ttl: [string, number][] = [["5V", 500], ["RX", 530], ["TX", 560], ["GND", 590]];
  const mains: [string, number][] = [["CT+", 450], ["CT−", 480], ["L", 540], ["N", 570]];
  return (
    <g>
      <text x={1125} y={418} textAnchor="middle" fontSize="12" fontWeight="bold" fill={t.text}>A8 · PZEM-004T v3.0, 100 А</text>
      <rect x={990} y={428} width={270} height={190} rx={6} fill="#0e7490" stroke="#155e75" strokeWidth="1.5" />
      {ttl.map(([name, y]) => (
        <g key={name}>
          <rect x={994} y={y - 6} width={12} height={12} fill="#111827" />
          <circle cx={1000} cy={y} r={3.5} fill="#d4a017" />
          <text x={1012} y={y + 3.5} fontSize="9" fill="#cffafe">{name}</text>
        </g>
      ))}
      {mains.map(([name, y]) => (
        <g key={name}>
          <rect x={1236} y={y - 9} width={20} height={18} rx={2} fill="#16a34a" stroke="#14532d" />
          <circle cx={1250} cy={y} r={3} fill="#d1d5db" />
          <text x={1230} y={y + 3.5} textAnchor="end" fontSize="9" fill="#cffafe">{name}</text>
        </g>
      ))}
      {[1060, 1100].map((x) => <rect key={x} x={x} y={500} width={26} height={16} rx={2} fill="#111827" />)}
      <text x={1086} y={536} textAnchor="middle" fontSize="7.5" fill="#cffafe">оптопары</text>
      <rect x={1130} y={560} width={46} height={30} rx={2} fill="#111827" />
      <text x={1153} y={579} textAnchor="middle" fontSize="7" fill="#cffafe">MCU</text>
      <text x={1125} y={634} textAnchor="middle" fontSize="9" fill={t.muted}>Modbus RTU 9600 8N1, адрес 0x01</text>
    </g>
  );
}

function Breaker({ x, y, label, t }: { x: number; y: number; label: string; t: Theme }) {
  return (
    <g>
      <rect x={x} y={y - 16} width={42} height={32} rx={3} fill="#e5e7eb" stroke="#6b7280" />
      <rect x={x + 16} y={y - 9} width={10} height={14} rx={1} fill="#1f2937" />
      <text x={x + 21} y={y + 30} textAnchor="middle" fontSize="9.5" fontWeight="bold" fill={t.text}>{label}</text>
    </g>
  );
}

export default function PanelMeterWiring({ isDark, className }: { isDark: boolean; className?: string }) {
  const t = theme(isDark);
  return (
    <svg viewBox="0 0 1500 1000" className={className} role="img" aria-label="Схема подключения узла учёта сети">
      <rect width="1500" height="1000" rx="12" fill={t.bg} />
      <Title t={t} title="Узел учёта сети — схема подключения" sub="A7: ESP32-DevKitC-32U + A8 PZEM-004T 100 А · щиток дома"
        source="по листу 9 документации котельной (07g-panel-node.svg)" />

      <Board t={t} designator="A7" name="ESP32-DevKitC-32U" antenna="" ipex />

      {/* external antenna on a cable: out of the metal panel */}
      <path d="M796,164 V124 H572" fill="none" stroke="#6b7280" strokeWidth="3" strokeLinecap="round" />
      <rect x={556} y={50} width={14} height={82} rx={6} fill="#111827" stroke="#4b5563" />
      <rect x={552} y={124} width={22} height={12} rx={2} fill="#4b5563" />
      <text x={544} y={78} textAnchor="end" fontSize="11" fontWeight="bold" fill={t.text}>антенна 2,4 ГГц на кабеле IPEX</text>
      <text x={544} y={94} textAnchor="end" fontSize="9.5" fill={t.muted}>вывести наружу металлического щитка —</text>
      <text x={544} y={108} textAnchor="end" fontSize="9.5" fill={t.muted}>внутри него Wi‑Fi не будет</text>

      {/* power at the board */}
      <Wire d={`M${XL},${rowY("3V3", "L")} H624`} color="#f97316" />
      <Tag x={576} y={rowY("3V3", "L")} net="+3V3" t={t} />
      <Wire d={`M${XL},${rowY("5V", "L")} H624`} color="#dc2626" />
      <Tag x={566} y={rowY("5V", "L")} net="+5V" t={t} w={56} label="+5V G3" />
      <Wire d={`M${XR},${rowY("GND", "R")} H896`} color={t.gnd} />
      <Tag x={896} y={rowY("GND", "R")} net="GND" t={t} />

      {/* UART2 ↔ PZEM TTL side */}
      <Pzem t={t} />
      <Wire d={`M${XR},${rowY("IO17", "R")} H1000`} color={TX} />
      <Wire d={`M${XR},${rowY("IO16", "R")} H1000`} color={RX} />
      <text x={935} y={rowY("IO17", "R") - 7} textAnchor="middle" fontSize="9" fontWeight="bold" fill={TX}>TX2 →</text>
      <text x={935} y={rowY("IO16", "R") + 16} textAnchor="middle" fontSize="9" fontWeight="bold" fill={RX}>← RX2</text>
      <Wire d="M1000,500 H976" color="#f97316" w={3} />
      <Tag x={930} y={500} net="+3V3" t={t} />
      <Wire d="M1000,590 H976" color={t.gnd} w={3} />
      <Tag x={930} y={590} net="GND" t={t} />

      {/* mains: L and N from the house main breaker to the loads */}
      <text x={1478} y={150} textAnchor="end" fontSize="10" fontWeight="bold" fill={t.text}>от вводного автомата дома</text>
      <Wire d={`M${XLINE},162 V930`} color={L_COL} w={5} />
      <Wire d={`M${XN},162 V930`} color={N_COL} w={5} />
      <text x={XLINE} y={176} textAnchor="end" dx={-8} fontSize="11" fontWeight="bold" fill={L_COL}>L</text>
      <text x={XN} y={176} dx={8} fontSize="11" fontWeight="bold" fill={N_COL}>N</text>
      <text x={1425} y={952} textAnchor="middle" fontSize="10" fontWeight="bold" fill={t.text}>↓ к нагрузкам дома</text>

      {/* TA1: split-core clamp on the phase only */}
      <rect x={XLINE - 16} y={236} width={32} height={44} rx={12} fill="none" stroke="#111827" strokeWidth="7" />
      <rect x={XLINE - 16} y={236} width={32} height={44} rx={12} fill="none" stroke="#9ca3af" strokeWidth="2" />
      <text x={1384} y={198} textAnchor="end" fontSize="10.5" fontWeight="bold" fill={t.text}>TA1 · 100 А, разъёмный</text>
      <text x={1384} y={212} textAnchor="end" fontSize="9" fill={t.muted}>на фазу, стрелкой ↓ к нагрузке</text>
      <Wire d="M1386,252 H1320 V450 H1250" color="#facc15" w={2.5} />
      <Wire d="M1386,264 H1345 V480 H1250" color="#a3a3a3" w={2.5} />
      <text x={1310} y={300} textAnchor="end" fontSize="9" fill={t.muted}>провода клещей</text>

      {/* voltage: L → QF7 → FU1 → A8 L; QF7 → G3 */}
      <circle cx={XLINE} cy={720} r={4} fill={L_COL} />
      <Wire d={`M${XLINE},720 H1372`} color={L_COL} w={3} />
      <Breaker x={1330} y={720} label="QF7 C2" t={t} />
      <Wire d="M1330,720 H1300" color={L_COL} w={3} />
      <circle cx={1300} cy={720} r={4} fill={L_COL} />
      <Wire d="M1300,720 V652 M1300,612 V540 H1250" color={L_COL} w={3} />
      <rect x={1291} y={612} width={18} height={40} rx={3} fill="#e5e7eb" stroke="#6b7280" />
      <rect x={1296} y={622} width={8} height={20} fill="#fbbf24" />
      <text x={1316} y={636} fontSize="9.5" fontWeight="bold" fill={t.text}>FU1 1 А</text>
      <circle cx={XN} cy={570} r={4} fill={N_COL} />
      <path d={nTap(570, 1250)} fill="none" stroke={N_COL} strokeWidth="3" strokeLinecap="round" />

      {/* G3: 5 V supply of the node, no battery */}
      <rect x={990} y={760} width={260} height={84} rx={6} fill="#94a3b8" stroke="#475569" strokeWidth="1.5" />
      <text x={1120} y={796} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#1f2937">G3 · БП 5 В, 2 А на DIN</text>
      <text x={1120} y={814} textAnchor="middle" fontSize="9.5" fill="#334155">без резерва: гаснет вместе с сетью</text>
      {[["+V", 780], ["−V", 820]].map(([n, y]) => (
        <g key={n as string}>
          <rect x={994} y={(y as number) - 8} width={20} height={16} rx={2} fill="#e5e7eb" stroke="#475569" />
          <text x={1004} y={(y as number) + 4} textAnchor="middle" fontSize="8.5" fontWeight="bold" fill="#1f2937">{n}</text>
        </g>
      ))}
      {[["L", 780], ["N", 820]].map(([n, y]) => (
        <g key={n as string}>
          <rect x={1226} y={(y as number) - 8} width={20} height={16} rx={2} fill="#e5e7eb" stroke="#475569" />
          <text x={1236} y={(y as number) + 4} textAnchor="middle" fontSize="8.5" fontWeight="bold" fill="#1f2937">{n}</text>
        </g>
      ))}
      <Wire d="M1300,720 V780 H1246" color={L_COL} w={3} />
      <circle cx={XN} cy={820} r={4} fill={N_COL} />
      <path d={nTap(820, 1246)} fill="none" stroke={N_COL} strokeWidth="3" strokeLinecap="round" />
      <Wire d="M994,780 H970" color="#dc2626" w={3} />
      <Tag x={924} y={780} net="+5V" t={t} />
      <Wire d="M994,820 H970" color={t.gnd} w={3} />
      <Tag x={924} y={820} net="GND" t={t} />

      <InfoBox x={40} y={170} w={500} t={t} title="Что меряет и публикует" lines={[
        "весь ввод дома (однофазный): напряжение, частота, ток,",
        "мощность, cos φ, кВт·ч — раз в 10 с",
        "MQTT: home/devices/<имя>/heartbeat — mains_v, mains_hz,",
        "mains_a, mains_w, mains_kwh, mains_pf",
        "Wi‑Fi прямо в брокер, без RF-шлюза",
      ]} />
      <InfoBox x={40} y={350} w={500} t={t} accent="#f97316" title="Монтаж — в щитке, 230 В" lines={[
        "TA1 — только на фазу после вводного автомата, N не пропускать",
        "напряжение на A8 — через QF7 (C2) и FU1 (1 А)",
        "TTL-сторону A8 питать от +3V3 платы: уровни ESP32",
        "работы в щитке — при снятом напряжении, электриком",
      ]} />
      <Legend x={24} y={790} w={540} t={t} nets={[
        ["+5V", "от G3 → вывод 5V платы A7 (резерва нет)"],
        ["+3V3", "со стабилизатора платы: TTL-сторона PZEM (вывод 5V модуля)"],
        ["GND", "общий минус низковольтной части"],
      ]} notes={[
        "• Пропажу света сообщают ИБП, не этот узел: он гаснет вместе с сетью.",
        "• Прошивка esp32-panel-meter — будущая (узел в планах).",
      ]} />
    </svg>
  );
}
