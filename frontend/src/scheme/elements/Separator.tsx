import { useId } from "react";

/**
 * Hydraulic separator (vertical) + distribution manifold.
 * Water colours: the separator fades from the boiler supply (top) to the boiler
 * return (bottom); the manifold's supply bar has the outgoing water colour,
 * the return bar the incoming one.
 */
export function Separator({ x, y, collectorWidth = 200, side = "right", supplyColor = "#fecaca", returnColor = "#bfdbfe" }: {
  x: number; y: number; collectorWidth?: number; side?: "left" | "right"; supplyColor?: string; returnColor?: string;
}) {
  const gradient = `sep-${useId().replace(/:/g, "")}`;
  const bx = side === "right" ? 36 : -collectorWidth;
  return (
    <g transform={`translate(${x} ${y})`}>
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={supplyColor} />
          <stop offset="1" stopColor={returnColor} />
        </linearGradient>
      </defs>
      <rect width={36} height={150} rx={10} fill={`url(#${gradient})`} fillOpacity={0.85} stroke="var(--scheme-stroke)" strokeWidth={2} />
      <rect x={14} y={-14} width={8} height={14} fill="#d97706" /> {/* air vent */}
      <rect data-bar="supply" x={bx} y={15} width={collectorWidth} height={30} rx={8} fill={supplyColor} fillOpacity={0.85} stroke="var(--scheme-stroke)" />
      <rect data-bar="return" x={bx} y={95} width={collectorWidth} height={30} rx={8} fill={returnColor} fillOpacity={0.85} stroke="var(--scheme-stroke)" />
    </g>
  );
}
