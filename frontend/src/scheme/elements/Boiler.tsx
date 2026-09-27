/** enabled: switched on (by hand or auto) — green dot; burning: the burner relay is on right now — flame. */
export function Boiler({ x, y, enabled, burning, auto, alarm }: {
  x: number; y: number; enabled: boolean; burning: boolean; auto: boolean; alarm: boolean;
}) {
  return (
    <g transform={`translate(${x} ${y})`} className={alarm ? "scheme-blink" : undefined}>
      <rect width={120} height={170} rx={12} fill="var(--scheme-device)" stroke={alarm ? "#dc2626" : "var(--scheme-stroke)"} strokeWidth={2} />
      <rect x={10} y={10} width={100} height={28} rx={5} fill="var(--scheme-panel)" />
      <circle data-part="led" cx={24} cy={24} r={5} fill={enabled ? "#22c55e" : "var(--scheme-muted)"} />
      <text x={36} y={29} fontSize={12} fontWeight={700} fill="var(--scheme-text)">Котёл</text>
      {/* flame window */}
      <rect x={35} y={70} width={50} height={60} rx={8} fill="var(--scheme-panel)" />
      {burning && (
        <path data-part="flame" d="M60 122 C45 108 52 92 60 80 C62 94 74 96 70 110 C68 118 64 121 60 122 Z" fill="#f97316" className="scheme-flicker" />
      )}
      <text x={60} y={155} fontSize={11} textAnchor="middle" fill="var(--scheme-muted)">{auto ? "авто" : "ручной"}</text>
      {/* vents */}
      {[0, 1, 2, 3, 4].map((i) => <rect key={i} x={20 + i * 18} y={160} width={10} height={3} fill="var(--scheme-muted)" />)}
    </g>
  );
}
