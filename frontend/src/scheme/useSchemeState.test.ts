import { describe, expect, it } from "vitest";
import { stillAwaiting } from "./useSchemeState";
import { makeState } from "./testing";

describe("stillAwaiting", () => {
  const appliedAt = Date.parse("2026-01-20T12:00:05Z");
  it("keeps fast polling while the state predates the apply", () => {
    const s = makeState();
    s.generated_at = "2026-01-20T12:00:03Z";
    expect(stillAwaiting(s, appliedAt)).toBe(true);
  });
  it("keeps fast polling while keys are pending", () => {
    const s = makeState();
    s.generated_at = "2026-01-20T12:00:09Z";
    s.sync.pending = ["heating_radiator_pump"];
    expect(stillAwaiting(s, appliedAt)).toBe(true);
  });
  it("stops once a newer state has nothing pending", () => {
    const s = makeState();
    s.generated_at = "2026-01-20T12:00:09Z";
    expect(stillAwaiting(s, appliedAt)).toBe(false);
  });
});
