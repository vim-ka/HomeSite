export function Pump({ x, y, running, r = 13 }: { x: number; y: number; running: boolean; r?: number }) {
  return (
    <g transform={`translate(${x} ${y})`} data-state={running ? "running" : "stopped"}>
      <circle r={r} fill="var(--scheme-device)" stroke={running ? "#16a34a" : "var(--scheme-muted)"} strokeWidth={3} />
      <g className={running ? "scheme-spin" : undefined}>
        <path d={`M0 ${-r * 0.65} L${r * 0.3} 0 L0 ${r * 0.65} L${-r * 0.3} 0 Z`} fill={running ? "#16a34a" : "var(--scheme-muted)"} />
        <path d={`M${-r * 0.65} 0 L0 ${r * 0.3} L${r * 0.65} 0 L0 ${-r * 0.3} Z`} fill={running ? "#16a34a" : "var(--scheme-muted)"} opacity={0.6} />
      </g>
    </g>
  );
}
