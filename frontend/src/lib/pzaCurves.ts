/**
 * PZA (погодозависимая автоматика) curves.
 * Outdoor temp points: [20, 10, 0, -10, -20, -35]°C
 */

export interface PZACurve {
  name: string;
  points: { outdoor: number; supply: number }[];
}

const OUTDOOR_TEMPS = [20, 10, 0, -10, -20, -35];

function makeCurves(data: number[][]): PZACurve[] {
  return data.map((supplies, i) => ({
    name: `Кривая ${i + 1}`,
    points: OUTDOOR_TEMPS.map((outdoor, j) => ({ outdoor, supply: supplies[j]! })),
  }));
}

/** Radiator PZA curves (5 curves, supply range ~20–85°C) */
export const RADIATOR_CURVES: PZACurve[] = makeCurves([
  [20, 29, 38, 44, 50, 55],
  [20, 32.5, 45, 52.5, 60, 67],
  [20, 34, 48, 56, 64, 70],
  [20, 36.5, 53, 61.5, 70, 78],
  [20, 39, 58, 67, 76, 85],
]);

/** Floor heating PZA curves (5 curves, supply range ~20–40°C) */
export const FLOOR_CURVES: PZACurve[] = makeCurves([
  [20, 22, 24, 26, 28, 29.5],
  [20, 23.5, 27, 29.5, 32, 34],
  [20, 23.5, 27, 30, 33, 36],
  [20, 24.5, 29, 32, 35, 38],
  [20, 25.5, 31, 34, 37, 40],
]);

/** @deprecated Use RADIATOR_CURVES instead */
export const PZA_CURVES = RADIATOR_CURVES;

/**
 * Linear interpolation to find supply temperature for a given outdoor temperature
 * on a specific PZA curve.
 */
export function interpolatePZA(curve: PZACurve, outdoorTemp: number): number {
  const pts = curve.points;

  if (outdoorTemp >= pts[0]!.outdoor) return pts[0]!.supply;
  if (outdoorTemp <= pts[pts.length - 1]!.outdoor)
    return pts[pts.length - 1]!.supply;

  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[i]!;
    const p1 = pts[i + 1]!;
    if (outdoorTemp <= p0.outdoor && outdoorTemp >= p1.outdoor) {
      const t = (p0.outdoor - outdoorTemp) / (p0.outdoor - p1.outdoor);
      return Math.round((p0.supply + t * (p1.supply - p0.supply)) * 10) / 10;
    }
  }

  return pts[0]!.supply;
}
