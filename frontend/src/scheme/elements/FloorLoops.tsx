/** Three spiral underfloor loops in one rounded frame (172×58 around x−6, y−6). */
export function FloorLoops({ x, y, warmth }: { x: number; y: number; warmth: number }) {
  const color = `rgba(239,68,68,${0.35 + 0.55 * Math.min(1, Math.max(0, warmth))})`;
  const spiral = "M4 4 H42 V42 H8 V10 H36 V36 H14 V16 H30 V30 H20 V22";
  return (
    <g transform={`translate(${x} ${y})`}>
      {/* one frame around the loops: the supply/return pipes end on its top edge (y − 6) */}
      <rect x={-6} y={-6} width={172} height={58} rx={10} fill="none" stroke="var(--scheme-muted)" strokeWidth={2} />
      {[0, 56, 112].map((dx) => (
        <path key={dx} d={spiral} transform={`translate(${dx} 0)`} fill="none" stroke={color} strokeWidth={2.5} />
      ))}
    </g>
  );
}
