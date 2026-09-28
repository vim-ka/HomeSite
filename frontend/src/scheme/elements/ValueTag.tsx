import type { Reading } from "../types";

export function ValueTag({ x, y, reading, unit, target, digits = 1, anchor = "start" }: {
  x: number; y: number; reading: Reading | undefined; unit: string; target?: number | null; digits?: number;
  /** "end": x is the right edge (mirrored layouts) */
  anchor?: "start" | "end";
}) {
  const ok = reading && !reading.stale && reading.value != null;
  const text = ok ? `${reading!.value!.toFixed(digits)}${unit}` : "—";
  const width = 14 + text.length * 7 + (target != null ? 26 : 0);
  return (
    <g transform={`translate(${anchor === "end" ? x - width : x} ${y})`}>
      <rect width={width} height={20} rx={3} fill="var(--scheme-tag-bg)" />
      <text x={6} y={14} fontSize={12} fontWeight={600} fill={ok ? "var(--scheme-tag-fg)" : "var(--scheme-muted)"}
            style={{ fontVariantNumeric: "tabular-nums" }}>
        {text}
      </text>
      {target != null && (
        <text x={10 + text.length * 7} y={14} fontSize={10} fill="var(--scheme-muted)">{`/${Math.round(target)}`}</text>
      )}
    </g>
  );
}
