const COLORS = { closed: "var(--scheme-muted)", opening: "#0ea5e9", closing: "#f59e0b", fault: "#dc2626" } as const;

export function FillValve({ x, y, state }: { x: number; y: number; state: keyof typeof COLORS }) {
  return (
    <g transform={`translate(${x} ${y})`} data-state={state} className={state === "fault" ? "scheme-blink" : undefined}>
      <polygon points="-10,-8 0,0 -10,8" fill={COLORS[state]} />
      <polygon points="10,-8 0,0 10,8" fill={COLORS[state]} />
      <rect x={-3} y={-18} width={6} height={10} fill={COLORS[state]} />
    </g>
  );
}
