/** Manometer; needle sweeps −120°..+120° over min..max; green arc = lo..hi. */
export function Gauge({ x, y, value, min = 0, max = 4, lo = null, hi = null }: {
  x: number; y: number; value: number | null; min?: number; max?: number; lo?: number | null; hi?: number | null;
}) {
  const angle = (v: number) => -120 + (240 * (Math.min(max, Math.max(min, v)) - min)) / (max - min);
  const polar = (deg: number, rad: number): [number, number] => {
    const a = ((deg - 90) * Math.PI) / 180;
    return [rad * Math.cos(a), rad * Math.sin(a)];
  };
  const arc = (from: number, to: number, rad: number) => {
    const [x1, y1] = polar(angle(from), rad);
    const [x2, y2] = polar(angle(to), rad);
    const large = angle(to) - angle(from) > 180 ? 1 : 0;
    return `M${x1} ${y1} A${rad} ${rad} 0 ${large} 1 ${x2} ${y2}`;
  };
  const [nx, ny] = polar(value == null ? -120 : angle(value), 13);
  return (
    <g transform={`translate(${x} ${y})`}>
      <circle r={18} fill="var(--scheme-device)" stroke="var(--scheme-stroke)" strokeWidth={2} />
      {lo != null && hi != null && <path d={arc(lo, hi, 15)} stroke="#22c55e" strokeWidth={3} fill="none" />}
      <line x1={0} y1={0} x2={nx} y2={ny} stroke="#dc2626" strokeWidth={2} strokeLinecap="round" />
      <circle r={2.5} fill="var(--scheme-stroke)" />
    </g>
  );
}
