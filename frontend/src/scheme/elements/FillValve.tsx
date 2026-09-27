const COLORS = { closed: "var(--scheme-muted)", opening: "#0ea5e9", closing: "#f59e0b", fault: "#dc2626" } as const;

/** Autofill ball valve; `enabled=false` (autofill switched off) is shown struck through. */
export function FillValve({ x, y, state, enabled = true }: { x: number; y: number; state: keyof typeof COLORS; enabled?: boolean }) {
  return (
    <g transform={`translate(${x} ${y})`} data-state={state} className={state === "fault" ? "scheme-blink" : undefined}>
      {!enabled && <line x1={-13} y1={11} x2={13} y2={-19} stroke="#dc2626" strokeWidth={2.5} strokeLinecap="round" />}
      <polygon points="-10,-8 0,0 -10,8" fill={COLORS[state]} />
      <polygon points="10,-8 0,0 10,8" fill={COLORS[state]} />
      <rect x={-3} y={-18} width={6} height={10} fill={COLORS[state]} />
    </g>
  );
}
