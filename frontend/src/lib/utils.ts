/**
 * Format a number with fixed decimal places, or return fallback for null/undefined.
 */
export function fmt(value: number | null | undefined, decimals = 1, fallback = "—"): string {
  if (value == null) return fallback;
  return value.toFixed(decimals);
}

/**
 * Format a timestamp string for display.
 */
export function fmtTime(ts: string): string {
  return new Date(ts).toLocaleString("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/**
 * CSS class merge helper.
 */
export function cn(...classes: (string | false | undefined | null)[]): string {
  return classes.filter(Boolean).join(" ");
}
