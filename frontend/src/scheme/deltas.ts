/**
 * Supply − return norms per circuit: green on the scheme inside them. The same thresholds raise the
 * efficiency advice on the backend (app/services/advice_rules.py) — change both together.
 */
export const DELTA_NORMS = {
  boiler: [8, 20],    // Beretta City 28 CSI: rated 80/60
  rad: [5, 25],
  floor: [3, 10],
  coil: [5, Infinity],   // at the start of a loading; while the tank is warm the difference shrinks by itself
} as const;

export type DeltaCircuit = keyof typeof DELTA_NORMS;

export function deltaOk(circuit: DeltaCircuit, d: number): boolean {
  const [lo, hi] = DELTA_NORMS[circuit];
  return d >= lo && d <= hi;
}
