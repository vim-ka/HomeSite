/**
 * Shared pieces of the pictorial wiring diagrams on the About page: the ESP32-DevKitC board with its two headers,
 * power tags (+5V / +3V3 / GND) and wires. All diagrams use the same 1500×1000 canvas and the board in the middle.
 */

// DevKitC header order, top (antenna end) to bottom (USB end) — same as docs/boiler-room/draw_schematic.py
export const LEFT = ["3V3", "EN", "IO36", "IO39", "IO34", "IO35", "IO32", "IO33", "IO25", "IO26", "IO27", "IO14", "IO12",
  "GND", "IO13", "SD2", "SD3", "CMD", "5V"];
export const RIGHT = ["GND", "IO23", "IO22", "TXD0", "RXD0", "IO21", "GND", "IO19", "IO18", "IO5", "IO17", "IO16", "IO4",
  "IO0", "IO2", "IO15", "SD1", "SD0", "CLK"];

export const PIN_Y0 = 230;
export const PITCH = 30;
export const XL = 650; // left header pads
export const XR = 870; // right header pads
export const rowY = (pin: string, side: "L" | "R") => PIN_Y0 + (side === "L" ? LEFT : RIGHT).indexOf(pin) * PITCH;

export interface Theme {
  bg: string; text: string; muted: string; gnd: string; gndText: string; panel: string; panelStroke: string;
}

export const theme = (dark: boolean): Theme => ({
  bg: dark ? "#0f172a" : "#f8fafc",
  text: dark ? "#e2e8f0" : "#1f2937",
  muted: dark ? "#94a3b8" : "#64748b",
  gnd: dark ? "#cbd5e1" : "#111827",
  gndText: dark ? "#0f172a" : "#ffffff",
  panel: dark ? "#1e293b" : "#ffffff",
  panelStroke: dark ? "#334155" : "#cbd5e1",
});

export type Net = "+5V" | "+3V3" | "GND";

export function Tag({ x, y, net, t, w = 46, label }: { x: number; y: number; net: Net; t: Theme; w?: number; label?: string }) {
  const fill = net === "+5V" ? "#dc2626" : net === "+3V3" ? "#f97316" : t.gnd;
  const color = net === "GND" ? t.gndText : "#ffffff";
  return (
    <g>
      <rect x={x} y={y - 9} width={w} height={18} rx={4} fill={fill} />
      <text x={x + w / 2} y={y + 4} textAnchor="middle" fontSize="10.5" fontWeight="bold" fill={color}>{label ?? net}</text>
    </g>
  );
}

export function Wire({ d, color, w = 4 }: { d: string; color: string; w?: number }) {
  return <path d={d} fill="none" stroke={color} strokeWidth={w} strokeLinecap="round" strokeLinejoin="round" />;
}

export function Board({ t, designator = "A1", name = "ESP32-DevKitC", antenna = "антенна — сюда, подальше от металла" }: {
  t: Theme; designator?: string; name?: string; antenna?: string;
}) {
  return (
    <g>
      <rect x={632} y={140} width={256} height={690} rx={10} fill="#111827" stroke="#374151" strokeWidth="2" />
      {/* WROOM-32 module with the PCB antenna on top */}
      <rect x={712} y={150} width={96} height={40} fill="#0b1220" />
      <path d="M720,182 v-24 h10 v18 h10 v-18 h10 v18 h10 v-18 h10 v18 h10 v-18 h10 v24" fill="none" stroke="#d4a017" strokeWidth="2" />
      <rect x={712} y={190} width={96} height={190} rx={3} fill="#9ca3af" stroke="#6b7280" />
      <text x={760} y={285} textAnchor="middle" fontSize="11" fontWeight="bold" fill="#1f2937" transform="rotate(-90 760 285)">ESP32-WROOM-32</text>
      <text x={760} y={470} textAnchor="middle" fontSize="13" fontWeight="bold" fill="#e5e7eb">{designator}</text>
      <text x={760} y={488} textAnchor="middle" fontSize="10" fill="#9ca3af">{name}</text>
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
      <text x={760} y={128} textAnchor="middle" fontSize="10" fill={t.muted}>{antenna}</text>
    </g>
  );
}

/** Panel with a bold title and plain lines (first line at y + 24, 15 px apart). */
export function InfoBox({ x, y, w, title, lines, t, accent }: {
  x: number; y: number; w: number; title: string; lines: string[]; t: Theme; accent?: string;
}) {
  const h = 36 + lines.length * 15;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8} fill={t.panel} stroke={accent ?? t.panelStroke}
        strokeDasharray={accent ? "6,4" : undefined} />
      <text x={x + 16} y={y + 24} fontSize="12" fontWeight="bold" fill={t.text}>{title}</text>
      {lines.map((line, i) => (
        <text key={i} x={x + 16} y={y + 44 + i * 15} fontSize="10.5" fill={t.muted}>{line}</text>
      ))}
    </g>
  );
}

/** "Как читать" box: what each power tag is fed from, then bullet notes. */
export function Legend({ x, y, w, nets, notes, t }: {
  x: number; y: number; w: number; nets: [Net, string][]; notes: string[]; t: Theme;
}) {
  const h = 44 + nets.length * 22 + notes.length * 15 + 8;
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8} fill={t.panel} stroke={t.panelStroke} />
      <text x={x + 16} y={y + 24} fontSize="12" fontWeight="bold" fill={t.text}>Как читать</text>
      {nets.map(([net, text], i) => (
        <g key={net}>
          <Tag x={x + 16} y={y + 44 + i * 22} net={net} t={t} />
          <text x={x + 70} y={y + 48 + i * 22} fontSize="10.5" fill={t.text}>{text}</text>
        </g>
      ))}
      {notes.map((line, i) => (
        <text key={i} x={x + 16} y={y + 44 + nets.length * 22 + 6 + i * 15} fontSize="10.5" fill={t.text}>{line}</text>
      ))}
    </g>
  );
}

/** Diagram title block, top right (same place on every wiring picture). */
export function Title({ title, sub, source, t }: { title: string; sub: string; source: string; t: Theme }) {
  return (
    <g>
      <text x={1180} y={58} textAnchor="middle" fontSize="22" fontWeight="bold" fill={t.text}>{title}</text>
      <text x={1180} y={84} textAnchor="middle" fontSize="12" fill={t.muted}>{sub}</text>
      <text x={1180} y={104} textAnchor="middle" fontSize="11" fill={t.muted}>{source}</text>
    </g>
  );
}

/** D-sub 9 connector seen from the mating side, standing vertically; pins 1–5 in the left column. */
export function Db9({ x, y, label, male, t }: { x: number; y: number; label: string; male: boolean; t: Theme }) {
  return (
    <g>
      <path d={`M${x},${y - 38} h30 l-4,76 h-22 z`} fill="#9ca3af" stroke="#4b5563" strokeWidth="1.2" />
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={`a${i}`}>
          <circle cx={x + 10} cy={y - 28 + i * 14} r={male ? 3 : 3.4} fill={male ? "#fbbf24" : "#1f2937"} />
          <text x={x - 4} y={y - 25 + i * 14} textAnchor="end" fontSize="8" fill={t.muted}>{i + 1}</text>
        </g>
      ))}
      {[0, 1, 2, 3].map((i) => (
        <circle key={`b${i}`} cx={x + 20} cy={y - 21 + i * 14} r={male ? 3 : 3.4} fill={male ? "#fbbf24" : "#1f2937"} />
      ))}
      <text x={x + 15} y={y + 52} textAnchor="middle" fontSize="9" fill={t.muted}>{label}</text>
    </g>
  );
}

/** Capacitor standing between the VCC wire (y1) and the GND wire (y2) (e.g. right at a module's pads). */
export function InlineCap({ x, y1, y2, electrolytic, t }: { x: number; y1: number; y2: number; electrolytic: boolean; t: Theme }) {
  const mid = (y1 + y2) / 2;
  return (
    <g>
      <Wire d={`M${x},${y1} V${y2}`} color={t.muted} w={2} />
      {electrolytic ? (
        <g>
          <rect x={x - 6} y={mid - 10} width={12} height={20} rx={2} fill="#1d4ed8" stroke="#1e3a8a" />
          <rect x={x + 2} y={mid - 10} width={4} height={20} fill="#93c5fd" />
        </g>
      ) : (
        <g>
          <ellipse cx={x} cy={mid} rx={7} ry={6.5} fill="#f59e0b" stroke="#b45309" strokeWidth="0.8" />
          <text x={x} y={mid + 2} textAnchor="middle" fontSize="5" fill="#451a03">104</text>
        </g>
      )}
      <circle cx={x} cy={y1} r={3} fill={t.text} />
      <circle cx={x} cy={y2} r={3} fill={t.text} />
    </g>
  );
}
