const ON = "#f97316";
const OFF = "#9ca3af";

/** Electric heater (ТЭН) at the bottom of the DHW tank, in the tank's own 80×190 coordinates. */
export function Teh({ on, switching = false }: { on: boolean; switching?: boolean }) {
  return (
    <g data-state={on ? "on" : "off"}>
      {/* invisible pad so the thin element is easy to click */}
      <rect x={12} y={140} width={56} height={44} fill="transparent" />
      <path d="M14 158 h6 l4 -8 l6 16 l6 -16 l6 16 l6 -16 l6 16 l4 -8 h6"
            fill="none" strokeWidth={3} strokeLinejoin="round" stroke={on ? ON : OFF}
            className={switching ? "scheme-teh-switching" : undefined} />
      <text x={40} y={180} fontSize={10} fontWeight={700} textAnchor="middle" fill={on ? ON : "var(--scheme-muted)"}>ТЭН</text>
    </g>
  );
}
