import { describe, expect, it } from "vitest";
import { manualHints } from "./hints";
import { makeState } from "./testing";

const at = (v: number) => ({ value: v, ts: "2026-01-20T12:00:00Z", stale: false });

describe("manualHints", () => {
  it("loading pump in manual mode keeps running although the tank is already hot", () => {
    const s = makeState();
    s.settings.watersupply_ihb_automode = "0";
    s.controller.relays.ihb_pump = true;
    s.controller.targets.ihb = 65;
    s.values.tank = at(66.8);
    const [hint] = manualHints(s);
    expect(hint!.element).toBe("ihb_pump");
    expect(hint!.text).toMatch(/ручном режиме.*уже нагрет/);

    s.values.tank = at(60);                       // still heating: the pump is doing its job
    expect(manualHints(s)).toEqual([]);
    s.values.tank = at(66.8);
    s.settings.watersupply_ihb_automode = "1";    // auto stops it by itself
    expect(manualHints(s)).toEqual([]);
  });

  it("TEH in manual mode heats together with the boiler", () => {
    const s = makeState();
    s.settings.watersupply_ihb_teh_automode = "0";
    s.controller.relays.teh = true;
    s.controller.relays.boiler = true;
    s.controller.relays.ihb_pump = true;
    expect(manualHints(s).map((h) => h.element)).toEqual(["teh"]);
    s.controller.relays.boiler = false;           // no gas heat: the TEH is the only source, fine
    expect(manualHints(s)).toEqual([]);
  });

  it("boiler in manual mode burns although the supply is at its setpoint", () => {
    const s = makeState();
    s.settings.heating_boiler_automode = "0";
    s.settings.heating_boiler_temp = "55";
    s.controller.relays.boiler = true;
    s.values.boiler_supply = at(57);
    expect(manualHints(s).map((h) => h.element)).toEqual(["boiler"]);
    s.values.boiler_supply = at(50);
    expect(manualHints(s)).toEqual([]);
  });

  it("stale readings or an offline controller give no hints", () => {
    const s = makeState();
    s.settings.watersupply_ihb_automode = "0";
    s.controller.relays.ihb_pump = true;
    s.controller.targets.ihb = 65;
    s.values.tank = { ...at(70), stale: true };
    expect(manualHints(s)).toEqual([]);
    s.values.tank = at(70);
    s.controller.online = false;
    expect(manualHints(s)).toEqual([]);
  });
});
