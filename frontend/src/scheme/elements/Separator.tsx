/** Hydraulic separator (vertical) + distribution manifold (supply bar top, return bar bottom). */
export function Separator({ x, y, collectorWidth = 200 }: { x: number; y: number; collectorWidth?: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect width={36} height={150} rx={10} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={2} />
      <rect x={14} y={-14} width={8} height={14} fill="#d97706" /> {/* air vent */}
      <rect x={36} y={15} width={collectorWidth} height={30} rx={8} fill="#fecaca" stroke="var(--scheme-stroke)" />
      <rect x={36} y={95} width={collectorWidth} height={30} rx={8} fill="#bfdbfe" stroke="var(--scheme-stroke)" />
    </g>
  );
}
