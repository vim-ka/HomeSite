/** Three spiral underfloor loops. */
export function FloorLoops({ x, y, warmth }: { x: number; y: number; warmth: number }) {
  const color = `rgba(239,68,68,${0.35 + 0.55 * Math.min(1, Math.max(0, warmth))})`;
  const spiral = "M4 4 H42 V42 H8 V10 H36 V36 H14 V16 H30 V30 H20 V22";
  return (
    <g transform={`translate(${x} ${y})`}>
      {[0, 56, 112].map((dx) => (
        <path key={dx} d={spiral} transform={`translate(${dx} 0)`} fill="none" stroke={color} strokeWidth={2.5} />
      ))}
    </g>
  );
}
