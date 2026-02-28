/**
 * PZA (погодозависимая автоматика) curves.
 * 5 curves x 6 data points each. X = outdoor temp, Y = supply temp.
 */

export interface PZACurve {
  name: string;
  points: { outdoor: number; supply: number }[];
}

export const PZA_CURVES: PZACurve[] = [
  {
    name: "Кривая 1",
    points: [
      { outdoor: -30, supply: 80 },
      { outdoor: -20, supply: 70 },
      { outdoor: -10, supply: 57 },
      { outdoor: 0, supply: 45 },
      { outdoor: 10, supply: 35 },
      { outdoor: 20, supply: 28 },
    ],
  },
  {
    name: "Кривая 2",
    points: [
      { outdoor: -30, supply: 75 },
      { outdoor: -20, supply: 65 },
      { outdoor: -10, supply: 53 },
      { outdoor: 0, supply: 42 },
      { outdoor: 10, supply: 33 },
      { outdoor: 20, supply: 27 },
    ],
  },
  {
    name: "Кривая 3",
    points: [
      { outdoor: -30, supply: 70 },
      { outdoor: -20, supply: 60 },
      { outdoor: -10, supply: 49 },
      { outdoor: 0, supply: 39 },
      { outdoor: 10, supply: 31 },
      { outdoor: 20, supply: 26 },
    ],
  },
  {
    name: "Кривая 4",
    points: [
      { outdoor: -30, supply: 65 },
      { outdoor: -20, supply: 55 },
      { outdoor: -10, supply: 45 },
      { outdoor: 0, supply: 36 },
      { outdoor: 10, supply: 29 },
      { outdoor: 20, supply: 25 },
    ],
  },
  {
    name: "Кривая 5",
    points: [
      { outdoor: -30, supply: 60 },
      { outdoor: -20, supply: 50 },
      { outdoor: -10, supply: 41 },
      { outdoor: 0, supply: 33 },
      { outdoor: 10, supply: 27 },
      { outdoor: 20, supply: 24 },
    ],
  },
];

/**
 * Linear interpolation to find supply temperature for a given outdoor temperature
 * on a specific PZA curve.
 */
export function interpolatePZA(curve: PZACurve, outdoorTemp: number): number {
  const pts = curve.points;

  // Clamp to curve range
  if (outdoorTemp <= pts[0]!.outdoor) return pts[0]!.supply;
  if (outdoorTemp >= pts[pts.length - 1]!.outdoor)
    return pts[pts.length - 1]!.supply;

  // Find segment
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i]!;
    const p1 = pts[i + 1]!;
    if (outdoorTemp >= p0.outdoor && outdoorTemp <= p1.outdoor) {
      const t = (outdoorTemp - p0.outdoor) / (p1.outdoor - p0.outdoor);
      return Math.round((p0.supply + t * (p1.supply - p0.supply)) * 10) / 10;
    }
  }

  return pts[0]!.supply;
}
