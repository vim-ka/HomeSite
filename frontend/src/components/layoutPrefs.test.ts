import { describe, expect, it, vi } from "vitest";
import { initialSidebarCollapsed } from "./layoutPrefs";

describe("initialSidebarCollapsed", () => {
  it("collapses the sidebar on phones and keeps it open on wide screens", () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q === "(max-width: 767px)" }));
    expect(initialSidebarCollapsed()).toBe(true);
    vi.stubGlobal("matchMedia", () => ({ matches: false }));
    expect(initialSidebarCollapsed()).toBe(false);
    vi.unstubAllGlobals();
  });
});
