/**
 * Parse a server timestamp as UTC.
 *
 * Server timestamps are UTC but may come without a zone ("2026-04-19T09:22:17")
 * or with a space separator ("2026-03-16 07:45:54"). Appending "Z" to the
 * space form gives a string Hermes can't parse (Invalid Date), so normalise
 * to ISO first.
 */
export function parseServerTs(ts: string): Date {
  let s = ts.trim().replace(" ", "T");
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(s)) s += "Z";
  return new Date(s);
}
