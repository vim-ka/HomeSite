export type PipeKind = "supply" | "return" | "cold" | "hot" | "fill";

const COLD = [0x3b, 0x82, 0xf6]; // #3b82f6
const HOT = [0xef, 0x44, 0x44];  // #ef4444
const KIND_DEFAULT: Record<PipeKind, string> = {
  supply: "#ef4444", return: "#3b82f6", cold: "#0ea5e9", hot: "#f97316", fill: "#0ea5e9",
};

const hex = (rgb: number[]) => "#" + rgb.map((c) => Math.round(c).toString(16).padStart(2, "0")).join("");

/** Pipe colour by water temperature: ≤25 °C blue → ≥70 °C red. */
export function pipeColor(temp: number | null | undefined, kind: PipeKind): string {
  if (temp == null || kind === "cold" || kind === "fill") return KIND_DEFAULT[kind];
  const t = Math.min(1, Math.max(0, (temp - 25) / 45));
  return hex(COLD.map((c, i) => c + (HOT[i]! - c) * t));
}
