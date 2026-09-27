import { describe, expect, it } from "vitest";
import { makeState } from "./testing";
import { toggleLock } from "./toggles";

describe("toggleLock", () => {
  it("TEH in auto mode is switched by the controller, not by a quick click", () => {
    expect(toggleLock("watersupply_ihb_teh_power", { watersupply_ihb_teh_automode: "1" })).toMatch(/ТЭН в авто-режиме/);
    expect(toggleLock("watersupply_ihb_teh_power", { watersupply_ihb_teh_automode: "0" })).toBeNull();
  });
});

describe("toggleLock: DHW priority", () => {
  const heatingTank = () => {
    const c = makeState().controller;
    c.flags.ihb_heating = true;
    c.relays.ihb_pump = true;
    return c;
  };

  it("a circuit pump can't be switched on while the tank heats with priority", () => {
    const s = { heating_radiator_off_ihb: "1" };
    expect(toggleLock("heating_radiator_pump", s, "1", heatingTank())).toMatch(/не включится — приоритет ГВС/);
    expect(toggleLock("heating_radiator_pump", s, "0", heatingTank())).toBeNull();   // switching off is fine
  });

  it("no priority for that circuit, or the tank isn't heating: no lock", () => {
    expect(toggleLock("heating_floorheating_pump", { heating_floorheating_off_ihb: "0" }, "1", heatingTank())).toBeNull();
    expect(toggleLock("heating_floorheating_pump", { heating_floorheating_off_ihb: "1" }, "1", makeState().controller)).toBeNull();
  });
});

describe("toggleLock: weather-compensated (ПЗА) circuits", () => {
  it("a circuit pump in ПЗА mode is not switched by a quick click, either way", () => {
    expect(toggleLock("heating_radiator_pump", { heating_radiator_wbm: "1" }, "0")).toBe(
      "Насос радиаторов в режиме ПЗА — сначала выключите ПЗА (правый клик)");
    expect(toggleLock("heating_floorheating_pump", { heating_floorheating_wbm: "1" }, "1")).toBe(
      "Насос тёплого пола в режиме ПЗА — сначала выключите ПЗА (правый клик)");
    expect(toggleLock("heating_radiator_pump", { heating_radiator_wbm: "0" }, "0")).toBeNull();
  });

  it("auto-mode wording for the tank pump stays as it was", () => {
    expect(toggleLock("watersupply_ihb_pump", { watersupply_ihb_automode: "1" })).toBe(
      "Насос бойлера в авто-режиме — управление по правому клику");
  });
});
