/**
 * Pictorial wiring diagram of the boiler room controller (A1): ESP32-DevKitC in the middle, coloured wires to the
 * two 8-channel relay modules, the sensors with their resistors / capacitors, and the 5 V supply.
 *
 * Source of truth: firmware/esp32-homesite/PINOUT.md and docs/boiler-room sheet 7 (07e-controller-logic.svg).
 * Power nets are drawn as coloured tags (+5V / +3V3 / GND) instead of long wires.
 */

// DevKitC header order, top (antenna end) to bottom (USB end) — same as docs/boiler-room/draw_schematic.py
const LEFT = ["3V3", "EN", "IO36", "IO39", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12",
  "GND", "IO13", "SD2", "SD3", "CMD", "5V"];
const RIGHT = ["GND", "IO23", "IO22", "TXD0", "RXD0", "IO21", "GND", "IO19", "IO18", "IO5", "IO17", "IO16", "IO4",
  "IO0", "IO2", "IO15", "SD1", "SD0", "CLK"];

const PIN_Y0 = 230;
const PITCH = 30;
const XL = 650; // left header pads
const XR = 870; // right header pads
const rowY = (pin: string, side: "L" | "R") => PIN_Y0 + (side === "L" ? LEFT : RIGHT).indexOf(pin) * PITCH;

const RIBBON_COLOURS = ["#ef4444", "#f97316", "#eab308", "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899"];
const ribbon = (i: number) => RIBBON_COLOURS[i % RIBBON_COLOURS.length] ?? "#64748b";

/** A2.1 (left): IN1…IN8 = K0…K6, K15 from the left header. Header y = 650 − (IN−1)·30; the jog x keeps the
 * ribbon flat (a lower wire turns nearer the board). */
const A21: { pin: string; k: number; load: string; jog: number | null }[] = [
  { pin: "IO13", k: 0, load: "котёл (клеммы ТА)", jog: null },
  { pin: "IO12", k: 1, load: "насос радиаторов M1", jog: 630 },
  { pin: "IO14", k: 2, load: "насос тёплого пола M2", jog: 615 },
  { pin: "IO27", k: 3, load: "насос загрузки БКН M3", jog: 600 },
  { pin: "IO26", k: 4, load: "насос скважины (KM2)", jog: 585 },
  { pin: "IO25", k: 5, load: "рециркуляция ГВС M5", jog: 570 },
  { pin: "IO33", k: 6, load: "ТЭН (через KM1)", jog: 555 },
  { pin: "IO32", k: 15, load: "запас → OpenTherm", jog: 540 },
];
/** A2.2 (right): IN1…IN8 = K7…K14 from the right header, in header order. Header y = 470 − (IN−1)·30. */
const A22: { pin: string; k: number; load: string; jog: number | null }[] = [
  { pin: "IO16", k: 7, load: "подпитка — открыть", jog: 975 },
  { pin: "IO17", k: 8, load: "подпитка — закрыть", jog: 960 },
  { pin: "IO5", k: 9, load: "3-ход радиаторов — открыть", jog: 945 },
  { pin: "IO18", k: 10, load: "3-ход радиаторов — закрыть", jog: 930 },
  { pin: "IO19", k: 11, load: "3-ход пола — открыть", jog: 915 },
  { pin: "IO21", k: 12, load: "3-ход пола — закрыть", jog: 900 },
  { pin: "IO22", k: 13, load: "лампа «Предупреждение»", jog: null },
  { pin: "IO23", k: 14, load: "лампа «Авария» + зуммер", jog: null },
];

interface Theme {
  bg: string; text: string; muted: string; gnd: string; gndText: string; panel: string; panelStroke: string;
}

const theme = (dark: boolean): Theme => ({
  bg: dark ? "#0f172a" : "#f8fafc",
  text: dark ? "#e2e8f0" : "#1f2937",
  muted: dark ? "#94a3b8" : "#64748b",
  gnd: dark ? "#cbd5e1" : "#111827",
  gndText: dark ? "#0f172a" : "#ffffff",
  panel: dark ? "#1e293b" : "#ffffff",
  panelStroke: dark ? "#334155" : "#cbd5e1",
});

type Net = "+5V" | "+3V3" | "GND";

function Tag({ x, y, net, t, w = 46, label }: { x: number; y: number; net: Net; t: Theme; w?: number; label?: string }) {
  const fill = net === "+5V" ? "#dc2626" : net === "+3V3" ? "#f97316" : t.gnd;
  const color = net === "GND" ? t.gndText : "#ffffff";
  return (
    <g>
      <rect x={x} y={y - 9} width={w} height={18} rx={4} fill={fill} />
      <text x={x + w / 2} y={y + 4} textAnchor="middle" fontSize="10.5" fontWeight="bold" fill={color}>{label ?? net}</text>
    </g>
  );
}

function Wire({ d, color, w = 4 }: { d: string; color: string; w?: number }) {
  return <path d={d} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />;
}

const BAND: Record<string, string> = {
  "2,2 кОм": "#dc2626,#dc2626,#dc2626", "10 кОм": "#78350f,#111827,#f97316", "100 Ом": "#78350f,#111827,#78350f",
};

/** Through-hole resistor centred at (x, y). */
function Resistor({ x, y, vertical = false, label, value, t }: {
  x: number; y: number; vertical?: boolean; label: string; value: string; t: Theme;
}) {
  const bands = (BAND[value] ?? "#78350f,#111827,#f97316").split(",");
  return (
    <g transform={`translate(${x} ${y})${vertical ? " rotate(90)" : ""}`}>
      <rect x={-17} y={-6} width={34} height={12} rx={5} fill="#e7c9a0" stroke="#a16207" strokeWidth="0.8" />
      {bands.map((c, i) => <rect key={i} x={-10 + i * 6} y={-6} width={3} height={12} fill={c} />)}
      <rect x={9} y={-6} width={3} height={12} fill="#ca8a04" />
      <g transform={vertical ? "rotate(-90)" : undefined}>
        <text x={vertical ? 14 : 0} y={vertical ? -2 : -11} textAnchor={vertical ? "start" : "middle"} fontSize="10" fontWeight="bold" fill={t.text}>{label}</text>
        <text x={vertical ? 14 : 0} y={vertical ? 10 : 21} textAnchor={vertical ? "start" : "middle"} fontSize="9.5" fill={t.muted}>{value}</text>
      </g>
    </g>
  );
}

/** Ceramic disc capacitor hanging from (x, y) down to y + 40, then a GND tag. */
function CapToGnd({ x, y, label, t }: { x: number; y: number; label: string; t: Theme }) {
  return (
    <g>
      <Wire d={`M${x},${y} V${y + 38}`} color={t.muted} w={2} />
      <ellipse cx={x} cy={y + 18} rx={8} ry={7} fill="#f59e0b" stroke="#b45309" strokeWidth="0.8" />
      <text x={x} y={y + 21} textAnchor="middle" fontSize="6" fill="#451a03">104</text>
      <text x={x + 11} y={y + 16} fontSize="10" fontWeight="bold" fill={t.text}>{label}</text>
      <text x={x + 11} y={y + 27} fontSize="9" fill={t.muted}>100 нФ</text>
      <circle cx={x} cy={y} r={3} fill={t.text} />
      <Tag x={x - 18} y={y + 47} net="GND" t={t} w={36} />
    </g>
  );
}

/** Zener (glass body, black band at the cathode = signal side) from (x, y) down to a GND tag. */
function ZenerToGnd({ x, y, label, t }: { x: number; y: number; label: string; t: Theme }) {
  return (
    <g>
      <Wire d={`M${x},${y} V${y + 38}`} color={t.muted} w={2} />
      <rect x={x - 5} y={y + 9} width={10} height={20} rx={3} fill="#fb923c" stroke="#c2410c" strokeWidth="0.8" />
      <rect x={x - 5} y={y + 9} width={10} height={4} fill="#111827" />
      <text x={x + 9} y={y + 16} fontSize="10" fontWeight="bold" fill={t.text}>{label}</text>
      <text x={x + 9} y={y + 27} fontSize="9" fill={t.muted}>3,6 В</text>
      <circle cx={x} cy={y} r={3} fill={t.text} />
      <Tag x={x - 18} y={y + 47} net="GND" t={t} w={36} />
    </g>
  );
}

/** Pressure sensor YD4060 (pictorial) whose signal lead ends at (x + 135, y). */
function PressureSensor({ x, y, name, sub, t }: { x: number; y: number; name: string; sub: string; t: Theme }) {
  return (
    <g>
      <rect x={x} y={y - 14} width={18} height={28} fill="#9ca3af" stroke="#4b5563" />
      {[0, 6, 12, 18, 24].map((d) => <line key={d} x1={x} y1={y - 14 + d + 2} x2={x + 18} y2={y - 14 + d + 4} stroke="#4b5563" strokeWidth="1" />)}
      <path d={`M${x + 18},${y - 22} h18 l8,8 v28 l-8,8 h-18 z`} fill="#d1d5db" stroke="#4b5563" />
      <rect x={x + 44} y={y - 18} width={56} height={36} rx={6} fill="#cbd5e1" stroke="#475569" />
      <text x={x + 72} y={y + 4} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#334155">YD4060</text>
      <rect x={x + 100} y={y - 8} width={14} height={16} rx={2} fill="#111827" />
      <Wire d={`M${x + 114},${y} H${x + 135}`} color="#06b6d4" />
      <Wire d={`M${x + 108},${y + 8} V${y + 34} H${x + 40}`} color="#dc2626" w={3} />
      <Wire d={`M${x + 112},${y + 8} V${y + 34} H${x + 160}`} color={t.gnd} w={3} />
      <Tag x={x - 6} y={y + 34} net="+5V" t={t} />
      <Tag x={x + 160} y={y + 34} net="GND" t={t} />
      <text x={x} y={y - 32} fontSize="11" fontWeight="bold" fill={t.text}>{name}<tspan dx="8" fontSize="9.5" fontWeight="normal" fill={t.muted}>{sub}</tspan></text>
    </g>
  );
}

/** 8-channel relay module. side = "L": header on the right edge (pads at hx), terminals and loads on the left. */
function RelayModule({ side, hx, y0, title, chans, t }: {
  side: "L" | "R"; hx: number; y0: number; title: string; t: Theme;
  chans: { k: number; load: string }[]; // top to bottom = IN8…IN1
}) {
  const w = 250;
  const x = side === "L" ? hx + 10 - w : hx - 10;
  const relayX = side === "L" ? x + 62 : x + 88;
  const termX = side === "L" ? x + 6 : x + w - 34;
  const optoX = side === "L" ? hx - 58 : hx + 40;
  const labelX = side === "L" ? x - 8 : x + w + 8;
  const rows = chans.map((c, i) => ({ ...c, y: y0 + 30 + i * PITCH, inN: 8 - i }));
  const top = y0 - 15;
  const bottom = y0 + 30 + 8 * PITCH;
  return (
    <g>
      <rect x={x} y={top} width={w} height={bottom - top + 15} rx={8} fill="#1d4ed8" stroke="#1e3a8a" strokeWidth="1.5" />
      <text x={x + w / 2} y={top - 8} textAnchor="middle" fontSize="12" fontWeight="bold" fill={t.text}>{title}</text>
      {/* header: DC+, IN8…IN1, DC− (H/L trigger board, jumpers in H) */}
      {[["DC+", y0], ...rows.map((r) => [`IN${r.inN}`, r.y] as const), ["DC−", bottom]].map(([name, y]) => (
        <g key={name as string}>
          <rect x={hx - 6} y={(y as number) - 6} width={12} height={12} fill="#111827" />
          <circle cx={hx} cy={y as number} r={3.5} fill="#d4a017" />
          <text x={side === "L" ? hx - 12 : hx + 12} y={(y as number) + 3.5} textAnchor={side === "L" ? "end" : "start"} fontSize="9" fill="#dbeafe">{name}</text>
        </g>
      ))}
      {rows.map((r) => (
        <g key={r.k}>
          <rect x={optoX} y={r.y - 5} width={16} height={10} rx={1.5} fill="#111827" />
          <rect x={relayX} y={r.y - 12} width={80} height={24} rx={3} fill="#2563eb" stroke="#93c5fd" strokeWidth="0.8" />
          <text x={relayX + 40} y={r.y + 3.5} textAnchor="middle" fontSize="8" fill="#dbeafe">SRD-05VDC</text>
          <rect x={termX} y={r.y - 11} width={28} height={22} rx={2} fill="#16a34a" stroke="#14532d" strokeWidth="0.8" />
          {[0, 9, 18].map((d) => <circle key={d} cx={termX + 5 + d} cy={r.y} r={2.6} fill="#d1d5db" />)}
          <text x={labelX} y={r.y + 3.5} textAnchor={side === "L" ? "end" : "start"} fontSize="10.5" fill={t.text}>
            <tspan fontWeight="bold">K{r.k}</tspan> {r.load}
          </text>
        </g>
      ))}
    </g>
  );
}

function Board({ t }: { t: Theme }) {
  return (
    <g>
      <rect x={632} y={140} width={256} height={690} rx={10} fill="#111827" stroke="#374151" strokeWidth="2" />
      {/* WROOM-32 module with the PCB antenna on top */}
      <rect x={712} y={150} width={96} height={40} fill="#0b1220" />
      <path d="M720,182 v-24 h10 v18 h10 v-18 h10 v18 h10 v-18 h10 v18 h10 v-18 h10 v24" fill="none" stroke="#d4a017" strokeWidth="2" />
      <rect x={712} y={190} width={96} height={190} rx={3} fill="#9ca3af" stroke="#6b7280" />
      <text x={760} y={285} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#1f2937" transform="rotate(-90 760 285)">ESP32-WROOM-32</text>
      <text x={760} y={470} textAnchor="middle" fontSize="13" fontWeight="bold" fill="#e5e7eb">A1</text>
      <text x={760} y={488} textAnchor="middle" fontSize="10" fill="#9ca3af">ESP32-DevKitC</text>
      <rect x={742} y={600} width={36} height={36} rx={2} fill="#000" stroke="#4b5563" />
      <text x={760} y={622} textAnchor="middle" fontSize="7" fill="#9ca3af">USB-UART</text>
      {[[722, "EN"], [798, "BOOT"]].map(([x, n]) => (
        <g key={n as string}>
          <rect x={(x as number) - 9} y={752} width={18} height={18} rx={2} fill="#d1d5db" />
          <circle cx={x as number} cy={761} r={5} fill="#4b5563" />
          <text x={x as number} y={784} textAnchor="middle" fontSize="8" fill="#9ca3af">{n}</text>
        </g>
      ))}
      <rect x={738} y={800} width={44} height={34} rx={4} fill="#9ca3af" stroke="#6b7280" />
      {LEFT.map((p, i) => (
        <g key={`L${p}${i}`}>
          <circle cx={XL} cy={PIN_Y0 + i * PITCH} r={8} fill="#d4a017" stroke="#92400e" />
          <circle cx={XL} cy={PIN_Y0 + i * PITCH} r={3} fill="#111827" />
          <text x={XL + 14} y={PIN_Y0 + i * PITCH + 4} fontSize="10.5" fill="#e5e7eb" fontFamily="monospace">{p}</text>
        </g>
      ))}
      {RIGHT.map((p, i) => (
        <g key={`R${p}${i}`}>
          <circle cx={XR} cy={PIN_Y0 + i * PITCH} r={8} fill="#d4a017" stroke="#92400e" />
          <circle cx={XR} cy={PIN_Y0 + i * PITCH} r={3} fill="#111827" />
          <text x={XR - 14} y={PIN_Y0 + i * PITCH + 4} textAnchor="end" fontSize="10.5" fill="#e5e7eb" fontFamily="monospace">{p}</text>
        </g>
      ))}
      <text x={760} y={128} textAnchor="middle" fontSize="10" fill={t.muted}>антенна — сюда, подальше от металла</text>
    </g>
  );
}

export default function ControllerWiring({ isDark, className }: { isDark: boolean; className?: string }) {
  const t = theme(isDark);
  const leftHeaderX = 460;
  const rightHeaderX = 1060;

  return (
    <svg viewBox="0 0 1500 1000" className={className} role="img" aria-label="Схема подключения контроллера котельной">
      <rect width="1500" height="1000" rx="12" fill={t.bg} />

      <text x={1180} y={58} textAnchor="middle" fontSize="22" fontWeight="bold" fill={t.text}>Контроллер котельной — схема подключения</text>
      <text x={1180} y={84} textAnchor="middle" fontSize="12" fill={t.muted}>ESP32-DevKitC · 2 модуля реле × 8 · датчики · питание 5 В</text>
      <text x={1180} y={104} textAnchor="middle" fontSize="11" fill={t.muted}>по firmware/esp32-homesite/PINOUT.md и листу 7 документации котельной</text>

      <Board t={t} />

      {/* power at the board */}
      <Wire d={`M${XL},${rowY("3V3", "L")} H624`} color="#f97316" />
      <Tag x={576} y={rowY("3V3", "L")} net="+3V3" t={t} />
      <Wire d={`M${XL},${rowY("5V", "L")} H624`} color="#dc2626" />
      <Tag x={576} y={rowY("5V", "L")} net="+5V" t={t} />
      <Wire d={`M${XR},${rowY("GND", "R")} H896`} color={t.gnd} />
      <Tag x={896} y={rowY("GND", "R")} net="GND" t={t} />

      {/* ===== top left: gas contact and pressure sensors ===== */}
      {/* gas: the analyser is wireless (433 MHz) — it reaches HomeSite through the RF gateway, not this board */}
      <rect x={40} y={36} width={420} height={78} rx={8} fill={t.panel} stroke="#a78bfa" strokeDasharray="6,4" />
      <text x={56} y={60} fontSize="12" fontWeight="bold" fill={t.text}>Анализатор газа — беспроводной, 433 МГц</text>
      <text x={56} y={78} fontSize="10" fill={t.muted}>к контроллеру не подключается: сигнал принимает RF-шлюз (CC1101)</text>
      <text x={56} y={93} fontSize="10" fill={t.muted}>и передаёт в HomeSite по MQTT. IO39 свободен.</text>
      <text x={56} y={106} fontSize="9" fill="#a78bfa">отсечной клапан газа — от самого анализатора</text>

      {/* BP1 → IO34 */}
      <Wire d={`M${XL},${rowY("IO34", "L")} H540 V200 H205`} color="#06b6d4" />
      <Resistor x={300} y={200} label="R3" value="10 кОм" t={t} />
      <CapToGnd x={425} y={200} label="C3" t={t} />
      <ZenerToGnd x={480} y={200} label="VD1" t={t} />
      <PressureSensor x={70} y={200} name="BP1" sub="давление отопления" t={t} />

      {/* BP2 → IO35 */}
      <Wire d={`M${XL},${rowY("IO35", "L")} H520 V320 H205`} color="#14b8a6" />
      <Resistor x={300} y={320} label="R4" value="10 кОм" t={t} />
      <CapToGnd x={405} y={320} label="C4" t={t} />
      <ZenerToGnd x={460} y={320} label="VD2" t={t} />
      <PressureSensor x={70} y={320} name="BP2" sub="давление воды" t={t} />

      {/* ===== left: relay module A2.1 ===== */}
      {A21.map((c, i) => {
        const inN = i + 1;
        const yh = 650 - (inN - 1) * PITCH;
        const ye = rowY(c.pin, "L");
        // K0 goes through JP1: GPIO13 → pin 2, jumper 1–2, pin 1 → IN1
        const d = c.k === 0 ? `M${XL},${ye} H594 V658 M574,658 V${yh} H${leftHeaderX}`
          : c.jog === null ? `M${XL},${ye} H${leftHeaderX}` : `M${XL},${ye} H${c.jog} V${yh} H${leftHeaderX}`;
        return <Wire key={c.pin} d={d} color={ribbon(i)} />;
      })}
      {/* JP1: 3-pin header on the K0 line. Jumper 1–2 now (relay K0 → boiler TA terminals);
          2–3 after the boiler swap (GPIO13 = OpenTherm receive from adapter A3). */}
      <rect x={562} y={656} width={64} height={18} rx={2} fill="#111827" stroke="#4b5563" />
      {[[574, "1"], [594, "2"], [614, "3"]].map(([x, n]) => (
        <g key={n}>
          <rect x={(x as number) - 4} y={661} width={8} height={8} fill="#d4a017" />
          <text x={x as number} y={686} textAnchor="middle" fontSize="9" fontWeight="bold" fill={t.muted}>{n}</text>
        </g>
      ))}
      <rect x={565} y={658} width={38} height={14} rx={3} fill="#facc15" fillOpacity="0.85" stroke="#a16207" strokeWidth="1" />
      <text x={584} y={668.5} textAnchor="middle" fontSize="8" fontWeight="bold" fill="#422006">1–2</text>
      <text x={556} y={669} textAnchor="end" fontSize="10" fontWeight="bold" fill="#facc15">JP1</text>
      <path d="M614,669 V676 H626 V714 H560" fill="none" stroke="#a78bfa" strokeWidth="2.5" strokeDasharray="5,4" strokeLinecap="round" />
      <text x={555} y={712} textAnchor="end" fontSize="9.5" fontWeight="bold" fill="#a78bfa">OpenTherm A3 (приём)</text>
      <text x={555} y={724} textAnchor="end" fontSize="9" fill={t.muted}>2–3 после замены котла</text>

      <RelayModule side="L" hx={leftHeaderX} y0={410} title="A2.1 · модуль реле 8 кан." t={t}
        chans={[...A21].reverse().map(({ k, load }) => ({ k, load }))} />
      <Wire d="M466,410 H480" color="#dc2626" w={3} />
      <Tag x={480} y={410} net="+5V" t={t} />
      <Wire d="M466,680 H480" color={t.gnd} w={3} />
      <Tag x={480} y={680} net="GND" t={t} />
      <text x={226} y={711} fontSize="9.5" fill={t.muted}>перемычки H/L — в H</text>
      <text x={226} y={723} fontSize="9.5" fill={t.muted}>DC− — отдельно к −V G1</text>

      {/* ===== right: relay module A2.2 ===== */}
      {A22.map((c, i) => {
        const inN = i + 1;
        const yh = 470 - (inN - 1) * PITCH;
        const ye = rowY(c.pin, "R");
        const d = c.jog === null ? `M${XR},${ye} H${rightHeaderX}` : `M${XR},${ye} H${c.jog} V${yh} H${rightHeaderX}`;
        return <Wire key={c.pin} d={d} color={ribbon(i)} />;
      })}
      <RelayModule side="R" hx={rightHeaderX} y0={230} title="A2.2 · модуль реле 8 кан." t={t}
        chans={[...A22].reverse().map(({ k, load }) => ({ k, load }))} />
      <Wire d="M1042,230 H1054" color="#dc2626" w={3} />
      <Tag x={998} y={230} net="+5V" t={t} w={44} />
      <Wire d="M1042,500 H1054" color={t.gnd} w={3} />
      <Tag x={998} y={500} net="GND" t={t} w={44} />
      <text x={1050} y={528} fontSize="9.5" fill={t.muted}>перемычки H/L — в H · DC− — отдельно к −V G1</text>

      {/* ===== right bottom: DS18B20 bus and DHT22 ===== */}
      <Wire d={`M${XR},${rowY("IO4", "R")} H1440`} color="#eab308" />
      <circle cx={1020} cy={590} r={3} fill={t.text} />
      <Wire d="M1020,590 V642" color={t.muted} w={2} />
      <Resistor x={1020} y={612} vertical label="R1" value="2,2 кОм" t={t} />
      <Resistor x={975} y={590} label="R5" value="100 Ом" t={t} />
      <Tag x={997} y={650} net="+3V3" t={t} />
      <Wire d="M1132,612 H1440" color="#dc2626" w={3} />
      <Wire d="M1132,634 H1440" color={t.gnd} w={3} />
      <Tag x={1086} y={612} net="+3V3" t={t} />
      <Tag x={1086} y={634} net="GND" t={t} />
      {[[1180, "BK1", "котёл, подача"], [1290, "BK2", "котёл, обратка"], [1400, "BK3…BK10", "контуры, бак, ХВС"]].map(([x, n, s]) => {
        const cx = x as number;
        return (
          <g key={n as string}>
            <Wire d={`M${cx - 6},590 V660`} color="#eab308" w={2.5} />
            <Wire d={`M${cx},612 V660`} color="#dc2626" w={2.5} />
            <Wire d={`M${cx + 6},634 V660`} color={t.gnd} w={2.5} />
            {[cx - 6, cx, cx + 6].map((px) => <circle key={px} cx={px} cy={px === cx - 6 ? 590 : px === cx ? 612 : 634} r={2.5} fill={t.text} />)}
            <rect x={cx - 9} y={660} width={18} height={40} rx={4} fill="#374151" />
            <rect x={cx - 7} y={700} width={14} height={52} rx={7} fill="#cbd5e1" stroke="#64748b" />
            <text x={cx} y={772} textAnchor="middle" fontSize="11" fontWeight="bold" fill={t.text}>{n}</text>
            <text x={cx} y={786} textAnchor="middle" fontSize="9.5" fill={t.muted}>{s}</text>
          </g>
        );
      })}
      <text x={1310} y={808} textAnchor="middle" fontSize="10" fill={t.muted}>DS18B20 в гильзах · гирлянда до 10 шт., без лучей</text>

      <Wire d={`M${XR},${rowY("IO15", "R")} H1125 V860 H1257`} color="#a3a3a3" />
      <circle cx={925} cy={680} r={3} fill={t.text} />
      <Wire d="M925,680 V630" color={t.muted} w={2} />
      <Resistor x={925} y={658} vertical label="R2" value="10 кОм" t={t} />
      <Tag x={902} y={622} net="+3V3" t={t} />
      <rect x={1260} y={826} width={86} height={108} rx={6} fill="#f8fafc" stroke="#94a3b8" />
      {Array.from({ length: 6 }).map((_, r) => Array.from({ length: 5 }).map((__, c) => (
        <rect key={`${r}-${c}`} x={1270 + c * 14} y={836 + r * 12} width={9} height={7} rx={1} fill="#cbd5e1" />
      )))}
      {[["VCC", 840], ["DATA", 860], ["NC", 880], ["GND", 900]].map(([n, y]) => (
        <g key={n as string}>
          <circle cx={1260} cy={y as number} r={3} fill="#d4a017" />
          <text x={1266} y={(y as number) + 3} fontSize="7" fill="#334155">{n}</text>
        </g>
      ))}
      <Wire d="M1257,840 H1244" color="#dc2626" w={3} />
      <Tag x={1208} y={840} net="+3V3" t={t} w={36} />
      <Wire d="M1257,900 H1244" color={t.gnd} w={3} />
      <Tag x={1208} y={900} net="GND" t={t} w={36} />
      <text x={1358} y={866} fontSize="11" fontWeight="bold" fill={t.text}>BK11 · DHT22</text>
      <text x={1358} y={880} fontSize="9.5" fill={t.muted}>воздух котельной</text>
      <text x={1358} y={894} fontSize="9.5" fill={t.muted}>провод ≤ 1–2 м</text>

      {/* ===== bottom centre: power supply ===== */}
      <rect x={610} y={880} width={300} height={90} rx={6} fill="#94a3b8" stroke="#475569" />
      <text x={760} y={930} textAnchor="middle" fontSize="12" fontWeight="bold" fill="#0f172a">G1 · MeanWell HDR-30-5</text>
      <text x={760} y={948} textAnchor="middle" fontSize="10" fill="#1e293b">5 В, выход подстроить на 5,1 В</text>
      {[["L", 640], ["N", 668], ["PE", 696], ["+V", 830], ["−V", 870]].map(([n, x]) => (
        <g key={n as string}>
          <rect x={(x as number) - 10} y={884} width={20} height={20} rx={2} fill="#e2e8f0" stroke="#475569" />
          <text x={x as number} y={898} textAnchor="middle" fontSize="9" fontWeight="bold" fill="#0f172a">{n}</text>
        </g>
      ))}
      <Wire d="M640,884 V862 H560" color="#92400e" w={3} />
      <Wire d="M668,884 V852 H560" color="#2563eb" w={3} />
      <text x={562} y={844} fontSize="9.5" fill={t.muted}>230 В · QF3</text>
      {/* G1 outputs → filter C1 / C2 → +5V / GND of the controller */}
      <Wire d="M830,884 V850 H1050" color="#dc2626" />
      <Wire d="M870,884 V866 H922 V940 H1050" color={t.gnd} />
      <Tag x={1050} y={850} net="+5V" t={t} />
      <Tag x={1050} y={940} net="GND" t={t} />
      <text x={935} y={838} fontSize="11" fontWeight="bold" fill={t.text}>Фильтр питания платы</text>
      {[960, 1020].map((x) => (
        <g key={x}>
          <circle cx={x} cy={850} r={3.5} fill={t.text} />
          <circle cx={x} cy={940} r={3.5} fill={t.text} />
        </g>
      ))}
      <Wire d="M960,850 V880 M960,910 V940" color={t.muted} w={2} />
      <rect x={951} y={880} width={18} height={30} rx={3} fill="#1d4ed8" stroke="#1e3a8a" />
      <rect x={963} y={880} width={4} height={30} fill="#93c5fd" />
      <text x={958} y={899} textAnchor="middle" fontSize="8" fontWeight="bold" fill="#fff">+</text>
      <Wire d="M1020,850 V888 M1020,902 V940" color={t.muted} w={2} />
      <ellipse cx={1020} cy={895} rx={9} ry={8} fill="#f59e0b" stroke="#b45309" />
      <text x={1020} y={898} textAnchor="middle" fontSize="6.5" fill="#451a03">104</text>
      <text x={960} y={958} textAnchor="middle" fontSize="10" fontWeight="bold" fill={t.text}>C1</text>
      <text x={960} y={970} textAnchor="middle" fontSize="9" fill={t.muted}>100 мкФ</text>
      <text x={1020} y={958} textAnchor="middle" fontSize="10" fontWeight="bold" fill={t.text}>C2</text>
      <text x={1020} y={970} textAnchor="middle" fontSize="9" fill={t.muted}>100 нФ</text>

      {/* ===== bottom left: notes ===== */}
      <rect x={24} y={768} width={524} height={224} rx={8} fill={t.panel} stroke={t.panelStroke} />
      <text x={40} y={792} fontSize="12" fontWeight="bold" fill={t.text}>Как читать</text>
      <Tag x={40} y={812} net="+5V" t={t} />
      <text x={94} y={816} fontSize="10.5" fill={t.text}>от БП G1: плата (вывод 5V), модули реле (DC+), датчики давления</text>
      <Tag x={40} y={834} net="+3V3" t={t} />
      <text x={94} y={838} fontSize="10.5" fill={t.text}>со стабилизатора платы (≤ 300 мА): подтяжки, DS18B20, DHT22</text>
      <Tag x={40} y={856} net="GND" t={t} />
      <text x={94} y={860} fontSize="10.5" fill={t.text}>общий минус для всего</text>
      {[
        "• До монтажа: espefuse.py set_flash_voltage 3.3V — GPIO12 (K1) не сорвёт загрузку.",
        "• Питание платы — USB или 5 В от G1, не вместе: перед прошивкой снять 5 В.",
        "• Модули реле: перемычки H/L — в H; DC− — отдельным проводом к −V G1.",
        "• HIGH на IN = вкл. «Закрыть» приводов (K8/K10/K12) — через NC «открыть» (лист 8).",
        "• JP1 1–2 — реле котла K0 (сейчас); 2–3 и K15 (IO32) — OpenTherm после замены.",
        "• Давление: датчик → 10 кОм → у вывода 100 нФ и стабилитрон 3,6 В на GND.",
        "• Строгая принципиальная схема — docs/boiler-room, лист 7.",
      ].map((line, i) => (
        <text key={i} x={40} y={884 + i * 15} fontSize="10.5" fill={t.text}>{line}</text>
      ))}
    </svg>
  );
}
