import { useId } from "react";

/** Where the loading pipes meet the tank (tank's own 80×190 coordinates) and what flows in them. */
export interface CoilDef {
  /** Wall the coil's inlet and outlet go through */
  side: "left" | "right";
  inY: number; outY: number;
  supplyColor: string; returnColor: string;
  /** Loading pump runs: water moves through the coil */
  flowing: boolean;
}

const TURNS = 5;
const COIL_X0 = 14, COIL_X1 = 66;   // across the tank, clear of its rounded walls
const COIL_BOTTOM = 136;            // the TEH lives below

/**
 * The coil as a helix seen from the side, from the inlet down to the outlet: front half-turns go
 * one way, back half-turns (drawn dimmer, behind) come back. One path in the flow direction.
 */
export function coilPath(c: Pick<CoilDef, "side" | "inY" | "outY">): { front: string; back: string; all: string } {
  const wall = c.side === "left" ? 0 : 80;
  const near = c.side === "left" ? COIL_X0 : COIL_X1, far = c.side === "left" ? COIL_X1 : COIL_X0;
  const top = c.inY, bottom = Math.min(c.outY, COIL_BOTTOM);
  const pitch = (bottom - top) / TURNS;
  const rx = (COIL_X1 - COIL_X0) / 2, ry = pitch * 0.45;
  const sweepFront = c.side === "left" ? 1 : 0;
  let all = `M${wall} ${top} H${near}`;
  const front: string[] = [], back: string[] = [];
  for (let i = 0; i < TURNS; i++) {
    const y = top + i * pitch;
    front.push(`M${near} ${y} A${rx} ${ry} 0 0 ${sweepFront} ${far} ${y + pitch / 2}`);
    back.push(`M${far} ${y + pitch / 2} A${rx} ${ry} 0 0 ${1 - sweepFront} ${near} ${y + pitch}`);
    all += ` A${rx} ${ry} 0 0 ${sweepFront} ${far} ${y + pitch / 2} A${rx} ${ry} 0 0 ${1 - sweepFront} ${near} ${y + pitch}`;
  }
  // the outlet below the coil (the tall layout's return is lower than the TEH top): down along the wall side
  const tail = c.outY > bottom ? ` V${c.outY}` : "";
  const exit = ` H${wall}`;
  return {
    front: [`M${wall} ${top} H${near}`, ...front].join(" "),
    back: `${back.join(" ")} M${near} ${bottom}${tail}${exit}`,
    all: all + tail + exit,
  };
}

/** DHW tank with its coil; fill 0..1 = heat level (red top / blue bottom). The TEH is its own element (Teh). */
export function Tank({ x, y, fill, coil }: { x: number; y: number; fill: number; coil?: CoilDef }) {
  const id = useId().replace(/:/g, "");
  const hot = 190 * Math.min(1, Math.max(0.1, fill));
  const path = coil && coilPath(coil);
  return (
    <g transform={`translate(${x} ${y})`}>
      <defs>
        <linearGradient id={`tank-heat-${id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ef4444" />
          <stop offset={hot / 190} stopColor="#f97316" />
          <stop offset="1" stopColor="#3b82f6" />
        </linearGradient>
        {coil && (
          // the coil cools down on its way: inlet in the supply colour, outlet in the return colour
          <linearGradient id={`coil-${id}`} gradientUnits="userSpaceOnUse" x1="0" y1={coil.inY} x2="0" y2={coil.outY}>
            <stop offset="0" stopColor={coil.supplyColor} />
            <stop offset="1" stopColor={coil.returnColor} />
          </linearGradient>
        )}
      </defs>
      <rect width={80} height={190} rx={36} fill={`url(#tank-heat-${id})`} opacity={0.25} />
      {path && (
        <g data-part="coil" data-flowing={String(coil!.flowing)} fill="none" strokeLinecap="round">
          <path d={path.back} stroke={`url(#coil-${id})`} strokeWidth={2.5} opacity={0.45} />
          <path d={path.front} stroke={`url(#coil-${id})`} strokeWidth={3.5} />
          {coil!.flowing && (
            <path data-part="coil-flow" d={path.all} stroke="#fff" strokeOpacity={0.7} strokeWidth={1.5}
                  strokeLinecap="butt" strokeDasharray="4 14" className="scheme-flow" />
          )}
        </g>
      )}
      <rect width={80} height={190} rx={36} fill="none" stroke="var(--scheme-stroke)" strokeWidth={2} />
    </g>
  );
}
