import { DIAL_R, TAG_HEIGHT, dialAt, tagLeg, tagRect, tagWidth } from "../geometry";
import type { TagDef } from "../layouts";
import type { Reading } from "../types";

// thermometer scale: cold → warm → hot, as a share of min..max
const TEMP_BANDS = [[0, 0.35, "#3b82f6"], [0.35, 0.65, "#f59e0b"], [0.65, 1, "#ef4444"]] as const;

/** Needle angle: −120°..+120° over min..max (same sweep as the heating manometer) */
const polar = (share: number, rad: number): [number, number] => {
  const a = ((-120 + 240 * Math.min(1, Math.max(0, share)) - 90) * Math.PI) / 180;
  return [rad * Math.cos(a), rad * Math.sin(a)];
};
const arc = (from: number, to: number, rad: number) => {
  const [x1, y1] = polar(from, rad);
  const [x2, y2] = polar(to, rad);
  return `M${x1} ${y1} A${rad} ${rad} 0 ${(to - from) * 240 > 180 ? 1 : 0} 1 ${x2} ${y2}`;
};

const ZONE_OK = "#22c55e", ZONE_BAD = "#ef4444";

/**
 * Round dial instrument: a thermometer (colour scale) or a manometer. A manometer with a working range
 * (lo..hi) shows it green and the rest of the scale red.
 */
export function Dial({ x, y, value, min, max, kind, lo = null, hi = null }: {
  x: number; y: number; value: number | null; min: number; max: number; kind: "temp" | "pressure";
  lo?: number | null; hi?: number | null;
}) {
  const at = (v: number) => (v - min) / (max - min);
  const [nx, ny] = polar(value == null ? 0 : at(value), DIAL_R - 4);
  const zones = kind === "pressure" && lo != null && hi != null && lo < hi
    ? [[0, at(lo), ZONE_BAD], [at(lo), at(hi), ZONE_OK], [at(hi), 1, ZONE_BAD]] as const : null;
  const band = (a: number, b: number, color: string) => (
    <path key={`${a}-${color}`} data-zone={color === ZONE_OK ? "ok" : color === ZONE_BAD ? "bad" : undefined}
          d={arc(Math.max(0, a), Math.min(1, b), DIAL_R - 2.5)} stroke={color} strokeWidth={2} fill="none" />
  );
  return (
    <g data-part="dial" data-kind={kind} transform={`translate(${x} ${y})`} opacity={value == null ? 0.6 : 1}>
      <circle r={DIAL_R} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={1.5} />
      {kind === "temp" ? TEMP_BANDS.map(([a, b, color]) => band(a, b, color))
        : zones ? zones.filter(([a, b]) => b > a).map(([a, b, color]) => band(a, b, color))
        : <path d={arc(0, 1, DIAL_R - 2.5)} stroke="var(--scheme-muted)" strokeWidth={1.5} fill="none" />}
      {value != null && (
        <line data-part="needle" x1={0} y1={0} x2={nx} y2={ny} stroke="#dc2626" strokeWidth={1.75} strokeLinecap="round" />
      )}
      <circle r={1.75} fill="var(--scheme-stroke)" />
    </g>
  );
}

/** A reading on its pipe: a stem from the pipe to a dial, the value next to the dial. */
export function ValueTag({ tag, reading, unit, target, digits = 1, min = 0, max = 100, lo, hi }: {
  tag: TagDef; reading: Reading | undefined; unit: string; target?: number | null; digits?: number;
  /** dial scale and (manometer) working range */
  min?: number; max?: number; lo?: number | null; hi?: number | null;
}) {
  const ok = reading && !reading.stale && reading.value != null;
  const text = ok ? `${reading!.value!.toFixed(digits)}${unit}` : "—";
  const width = tagWidth(text.length, target != null);
  const { x, y } = tagRect(tag, width);
  const [[lx, ly], [px, py]] = tagLeg(tag);
  const [dx, dy] = dialAt(tag);
  return (
    <g>
      {tag.dial
        ? <>  {/* callout: a thin line from the sensor's point inside the device, a ring marks the point */}
            <line data-part="callout" x1={lx} y1={ly} x2={px} y2={py} stroke="var(--scheme-stroke)" strokeWidth={1.5} />
            <circle data-part="probe" cx={px} cy={py} r={3} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={1.5} />
          </>
        : <line data-part="stem" x1={lx} y1={ly} x2={px} y2={py} stroke="var(--scheme-stroke)" strokeWidth={3} />}
      <Dial x={dx} y={dy} value={ok ? reading!.value! : null} min={min} max={max} kind={unit === "°" ? "temp" : "pressure"}
            lo={lo} hi={hi} />
      <g transform={`translate(${x} ${y})`}>
        <rect width={width} height={TAG_HEIGHT} rx={3} fill="var(--scheme-tag-bg)" stroke="var(--scheme-stroke)" strokeOpacity={0.5} />
        {/* the target follows the value right after it: "65.8°/45°"; centred, so the padding is even */}
        <text x={width / 2} y={14} textAnchor="middle" fontSize={12} fontWeight={600}
              fill={ok ? "var(--scheme-tag-fg)" : "var(--scheme-muted)"} style={{ fontVariantNumeric: "tabular-nums" }}>
          {text}
          {target != null && <tspan data-part="target" fontSize={10} fontWeight={400} fill="var(--scheme-muted)">{`/${Math.round(target)}${unit}`}</tspan>}
        </text>
      </g>
    </g>
  );
}
