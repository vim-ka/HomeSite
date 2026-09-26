/** DHW tank with coil; fill 0..1 = heat level (red top / blue bottom), TEH element at the bottom. */
export function Tank({ x, y, fill, teh }: { x: number; y: number; fill: number; teh: boolean }) {
  const hot = 190 * Math.min(1, Math.max(0.1, fill));
  return (
    <g transform={`translate(${x} ${y})`}>
      <defs>
        <linearGradient id="tank-heat" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ef4444" />
          <stop offset={hot / 190} stopColor="#f97316" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
      </defs>
      <rect width={80} height={190} rx={36} fill="url(#tank-heat)" opacity={0.25} />
      <rect width={80} height={190} rx={36} fill="none" stroke="var(--scheme-stroke)" strokeWidth={2} />
      <path d="M20 60 q20 10 40 0 q-20 10 -40 20 q20 10 40 0 q-20 10 -40 20" fill="none" stroke="var(--scheme-muted)" strokeWidth={2} />
      <rect x={22} y={160} width={36} height={6} rx={3} fill={teh ? "#f97316" : "var(--scheme-muted)"} className={teh ? "scheme-blink" : undefined} />
    </g>
  );
}
