const STREAMS = { hot: "#ef4444", cold: "#0ea5e9" } as const;

/** Shower head on a riser (riser at x 0 ... spout on the right); streams coloured by the water it gives. */
export function Tap({ x, y, water = "hot" }: { x: number; y: number; water?: "hot" | "cold" }) {
  return (
    <g transform={`translate(${x} ${y})`} stroke="var(--scheme-stroke)" fill="none" strokeWidth={2}>
      <path d="M0 24 V6 H14" />
      <path d="M8 6 h14 l-3 6 h-8 Z" fill="var(--scheme-device)" />
      <path data-part="streams" d="M12 16 v4 M16 16 v5 M20 16 v4" stroke={STREAMS[water]} />
    </g>
  );
}
