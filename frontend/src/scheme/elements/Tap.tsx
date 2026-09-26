export function Tap({ x, y }: { x: number; y: number }) {
  return (
    <g transform={`translate(${x} ${y})`} stroke="var(--scheme-stroke)" fill="none" strokeWidth={2}>
      <path d="M0 24 V6 H14" />
      <path d="M8 6 h14 l-3 6 h-8 Z" fill="var(--scheme-device)" />
      <path d="M12 16 v4 M16 16 v5 M20 16 v4" stroke="#0ea5e9" />
    </g>
  );
}
