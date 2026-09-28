import { describe, expect, it } from "vitest";
import { pipeColor } from "./pipeColor";

describe("pipeColor", () => {
  it("is blue at or below 25 °C and red at or above 70 °C", () => {
    expect(pipeColor(10, "supply")).toBe("#3b82f6");
    expect(pipeColor(25, "supply")).toBe("#3b82f6");
    expect(pipeColor(70, "return")).toBe("#ef4444");
    expect(pipeColor(90, "return")).toBe("#ef4444");
  });
  it("interpolates in between", () => {
    const mid = pipeColor(47.5, "supply");
    expect(mid).not.toBe("#3b82f6");
    expect(mid).not.toBe("#ef4444");
    expect(mid).toMatch(/^#[0-9a-f]{6}$/);
  });
  it("falls back to the pipe kind colour without a value", () => {
    expect(pipeColor(null, "supply")).toBe("#ef4444");
    expect(pipeColor(undefined, "return")).toBe("#3b82f6");
    expect(pipeColor(null, "cold")).toBe("#0ea5e9");
    expect(pipeColor(null, "fill")).toBe("#0ea5e9");
    expect(pipeColor(null, "hot")).toBe("#f97316");
  });
});
