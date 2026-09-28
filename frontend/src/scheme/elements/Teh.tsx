const ON = "#f97316";
const OFF = "#9ca3af";

/**
 * Electric heater (ТЭН) at the bottom of the DHW tank, in the tank's own 80×190 coordinates.
 * enabled: switched on (by hand or auto) — orange; heating: its relay is on right now — heat waves above it.
 */
export function Teh({ enabled, heating, auto = false, switching = false }: {
  enabled: boolean; heating: boolean; auto?: boolean; switching?: boolean;
}) {
  const lit = enabled || heating;
  return (
    <g data-state={heating ? "on" : enabled ? "standby" : "off"}>
      {/* invisible pad so the thin element is easy to click */}
      <rect x={12} y={126} width={56} height={58} fill="transparent" />
      {heating && (
        // two waves rise from the element and fade, one after the other
        <g data-part="heat" fill="none" stroke={ON} strokeWidth={1.5} strokeLinecap="round">
          {[0, 1].map((i) => (
            <path key={i} className="scheme-heat" style={{ animationDelay: `${i * 0.8}s` }}
                  d="M16 146 q4 -4 8 0 t8 0 t8 0 t8 0 t8 0 t8 0" />
          ))}
        </g>
      )}
      <path data-part="element" d="M14 158 h6 l4 -8 l6 16 l6 -16 l6 16 l6 -16 l6 16 l4 -8 h6"
            fill="none" strokeWidth={3} strokeLinejoin="round" stroke={lit ? ON : OFF}
            className={switching ? "scheme-teh-switching" : undefined} />
      <text x={40} y={180} fontSize={10} fontWeight={700} textAnchor="middle" fill={lit ? ON : "var(--scheme-muted)"}>
        {auto ? "ТЭН авто" : "ТЭН"}
      </text>
    </g>
  );
}
