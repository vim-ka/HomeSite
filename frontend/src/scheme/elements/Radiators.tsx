/** Three sectional radiators; warmth 0..1 tints the fins. */
export function Radiators({ x, y, warmth }: { x: number; y: number; warmth: number }) {
  const tint = `rgba(239,68,68,${0.15 + 0.5 * Math.min(1, Math.max(0, warmth))})`;
  return (
    <g transform={`translate(${x} ${y})`}>
      {[0, 95, 190].map((dx) => (
        <g key={dx} transform={`translate(${dx} 0)`}>
          <rect width={70} height={46} rx={4} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" />
          {Array.from({ length: 7 }, (_, i) => (
            <rect key={i} x={5 + i * 9.3} y={4} width={6} height={38} rx={2} fill={tint} />
          ))}
        </g>
      ))}
    </g>
  );
}
