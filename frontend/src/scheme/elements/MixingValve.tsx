export function MixingValve({ x, y, direction }: { x: number; y: number; direction: "open" | "close" | null }) {
  const active = direction !== null;
  const fill = active ? "#f59e0b" : "var(--scheme-muted)";
  return (
    <g transform={`translate(${x} ${y})`} data-state={direction ?? "idle"}>
      <polygon points="-10,-8 0,0 -10,8" fill={fill} />
      <polygon points="10,-8 0,0 10,8" fill={fill} />
      <polygon points="-8,10 0,0 8,10" fill={fill} opacity={0.7} />
      {active && (
        <text x={14} y={4} fontSize={12} fill="#f59e0b" className="scheme-blink">
          {direction === "open" ? "↑" : "↓"}
        </text>
      )}
    </g>
  );
}
