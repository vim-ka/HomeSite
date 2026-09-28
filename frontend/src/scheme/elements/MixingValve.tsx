/**
 * 3-way mixing valve on a vertical pipe: two ports along the pipe (collector in, mixed water out),
 * the third towards the bypass; a chevron past the outlet shows where the mixed water goes.
 */
export function MixingValve({ x, y, direction, out = "up", bypass = "right" }: {
  x: number; y: number; direction: "open" | "close" | null;
  out?: "up" | "down"; bypass?: "left" | "right";
}) {
  const active = direction !== null;
  const fill = active ? "#f59e0b" : "var(--scheme-muted)";
  const o = out === "up" ? -1 : 1;     // outlet side along y
  const b = bypass === "right" ? 1 : -1;
  return (
    <g transform={`translate(${x} ${y})`} data-state={direction ?? "idle"} data-out={out} data-bypass={bypass}>
      <polygon points={`-8,${-10 * o} 8,${-10 * o} 0,0`} fill={fill} />
      <polygon points={`-8,${10 * o} 8,${10 * o} 0,0`} fill={fill} />
      <polygon points={`${10 * b},-8 ${10 * b},8 0,0`} fill={fill} opacity={0.7} />
      <path d={`M-5 ${13 * o} L0 ${18 * o} L5 ${13 * o}`} fill="none" stroke={fill} strokeWidth={2}
            strokeLinecap="round" strokeLinejoin="round" />
      {active && (
        <text x={-12 * b} y={4} fontSize={9} textAnchor={b > 0 ? "end" : "start"} fill="#f59e0b" className="scheme-blink">
          {direction === "open" ? "откр" : "закр"}
        </text>
      )}
    </g>
  );
}
