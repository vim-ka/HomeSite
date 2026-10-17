/**
 * Flat (butt) ends so a pipe stops exactly at a device outline; round joins at bends.
 * `cap`: the pipe ends in the open (at a tap) — a round knob in its colour finishes it.
 */
export function Pipe({ points, color, flowing, width = 6, cap = false }: {
  points: [number, number][]; color: string; flowing: boolean; width?: number; cap?: boolean;
}) {
  const [ex, ey] = points.at(-1)!;
  const d = points.map(([x, y], i) => `${i ? "L" : "M"}${x} ${y}`).join(" ");
  return (
    <g>
      <path d={d} fill="none" stroke={color} strokeWidth={width} strokeLinecap="butt" strokeLinejoin="round" />
      {/* light highlight gives the pipe some volume */}
      <path d={d} fill="none" stroke="#fff" strokeOpacity={0.25} strokeWidth={width / 3}
            strokeLinecap="butt" strokeLinejoin="round" transform={`translate(0 ${-width / 4})`} />
      {flowing && (
        <path d={d} fill="none" stroke="#fff" strokeOpacity={0.7} strokeWidth={width / 3} strokeLinecap="butt"
              strokeDasharray="4 14" className="scheme-flow" />
      )}
      {cap && <circle data-part="cap" cx={ex} cy={ey} r={width * 0.8} fill={color} stroke="var(--scheme-stroke)" strokeOpacity={0.6} />}
    </g>
  );
}
