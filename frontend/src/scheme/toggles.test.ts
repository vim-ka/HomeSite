import { describe, expect, it } from "vitest";
import { toggleLock } from "./toggles";

describe("toggleLock", () => {
  it("TEH in auto mode is switched by the controller, not by a quick click", () => {
    expect(toggleLock("watersupply_ihb_teh_power", { watersupply_ihb_teh_automode: "1" })).toMatch(/ТЭН в авто-режиме/);
    expect(toggleLock("watersupply_ihb_teh_power", { watersupply_ihb_teh_automode: "0" })).toBeNull();
  });
});
