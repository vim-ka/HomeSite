/**
 * Format a number with fixed decimal places, or return fallback for null/undefined.
 */
export function fmt(value: number | null | undefined, decimals = 1, fallback = "—"): string {
  if (value == null) return fallback;
  return value.toFixed(decimals);
}

/**
 * Parse a server timestamp as UTC.
 *
 * Server timestamps are UTC but may arrive without a zone ("2026-04-19T09:22:17"
 * or "2026-03-16 07:45:54" from SQLite); new Date() would read those as local time.
 */
export function parseServerTs(ts: string): Date {
  let s = ts.trim().replace(" ", "T");
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s += "Z";
  return new Date(s);
}

/**
 * Format a timestamp string for display.
 */
export function fmtTime(ts: string): string {
  return parseServerTs(ts).toLocaleString("ru-RU", {
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
