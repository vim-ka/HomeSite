const GREEN = "#16a34a";
const GREY = "#9ca3af";
/** One size for every pump on the scheme (the DHW loading pump's size). */
const R = 11;

/**
 * Circulation pump: a solid disc — green when running, grey when stopped —
 * with a white impeller that spins while it runs. While a switch command is
 * on its way the disc blinks grey/green.
 */
export function Pump({ x, y, running, switching = false }: { x: number; y: number; running: boolean; switching?: boolean }) {
  return (
    <g transform={`translate(${x} ${y})`} data-state={running ? "running" : "stopped"}>
      <circle data-part="disc" r={R} fill={running ? GREEN : GREY} className={switching ? "scheme-pump-switching" : undefined} />
      <g className={running ? "scheme-spin" : undefined}>
        <path d={`M0 ${-R * 0.65} L${R * 0.3} 0 L0 ${R * 0.65} L${-R * 0.3} 0 Z`} fill="#fff" />
        <path d={`M${-R * 0.65} 0 L0 ${R * 0.3} L${R * 0.65} 0 L0 ${-R * 0.3} Z`} fill="#fff" opacity={0.75} />
      </g>
    </g>
  );
}
