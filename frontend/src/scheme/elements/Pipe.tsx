/** Flat (butt) ends so a pipe stops exactly at a device outline; round joins at bends. */
export function Pipe({ points, color, flowing, width = 6 }: {
  points: [number, number][]; color: string; flowing: boolean; width?: number;
}) {
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
    </g>
  );
}
