/** Water well: ground line, casing going down to the water level, wellhead on top (50×80). */
export function Well({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <line x1={-6} y1={14} x2={56} y2={14} stroke="var(--scheme-stroke)" strokeWidth={2} />
      {[0, 10, 20, 30, 40, 50].map((dx) => (
        <line key={dx} x1={dx - 4} y1={22} x2={dx + 4} y2={14} stroke="var(--scheme-muted)" strokeWidth={1.5} />
      ))}
      <rect x={17} y={14} width={16} height={64} fill="var(--scheme-panel)" stroke="var(--scheme-stroke)" strokeWidth={1.5} />
      <rect x={18.5} y={52} width={13} height={24.5} fill="#0ea5e9" opacity={0.55} />
      <rect x={11} y={2} width={28} height={12} rx={2} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={2} />
    </g>
  );
}
