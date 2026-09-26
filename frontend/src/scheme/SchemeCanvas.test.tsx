import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { chooseLayout } from "./layouts";
import { SchemeCanvas } from "./SchemeCanvas";
import type { SchemeState } from "./types";

const reading = (value: number | null) => ({ value, ts: "2026-01-20T12:00:00Z", stale: false });

export function makeState(over: Partial<SchemeState["controller"]> = {}): SchemeState {
  const relays = Object.fromEntries(
    ["boiler", "rad_pump", "floor_pump", "ihb_pump", "water_pump", "water_hot_pump", "teh", "af_open", "af_close",
     "rad_open", "rad_close", "floor_open", "floor_close", "lamp_warning", "lamp_critical", "spare"].map((r) => [r, false]),
  ) as SchemeState["controller"]["relays"];
  return {
    generated_at: "2026-01-20T12:00:00Z",
    values: Object.fromEntries(
      ["boiler_supply", "boiler_return", "rad_supply", "rad_return", "floor_supply", "floor_return", "tank",
       "coil_return", "cold_water", "hot_water", "heating_pressure", "water_pressure", "outdoor", "indoor_avg",
       "boiler_room"].map((k) => [k, reading(40)]),
    ) as SchemeState["values"],
    controller: { online: true, last_seen: "2026-01-20T12:00:00Z", relays: { ...relays, rad_pump: true },
                  flags: {}, targets: { boiler: 56, rad: 54, floor: 29, ihb: 55 }, ...over },
    settings: { heating_boiler_automode: "1", heating_pressure_min: "1.0", heating_pressure_max: "2.0" },
    sync: { pending: [], unsynced: [] },
    alarms: [], events: [], stale_minutes: 5,
  };
}

describe("layouts", () => {
  it("picks the wide layout from 900 px", () => {
    expect(chooseLayout(1200)).toBe("wide");
    expect(chooseLayout(900)).toBe("wide");
    expect(chooseLayout(899)).toBe("tall");
  });
});

describe("SchemeCanvas", () => {
  for (const layout of ["wide", "tall"] as const) {
    it(`${layout}: radiator pump running, floor pump stopped`, () => {
      const { container } = render(<SchemeCanvas state={makeState()} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='rad_pump'] [data-state='running']")).not.toBeNull();
      expect(container.querySelector("[data-element='floor_pump'] [data-state='stopped']")).not.toBeNull();
    });
  }

  it("opens the circuit dialog on click and keyboard", () => {
    const onOpen = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} />);
    const rad = container.querySelector("[data-element='radiators']")!;
    fireEvent.click(rad);
    fireEvent.keyDown(rad, { key: "Enter" });
    expect(onOpen).toHaveBeenNthCalledWith(1, "rad", undefined);
    expect(onOpen).toHaveBeenCalledTimes(2);
  });

  it("dims everything when the controller is offline", () => {
    const { container } = render(<SchemeCanvas state={makeState({ online: false })} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-offline='true']")).not.toBeNull();
  });

  it("shows night and DHW priority badges", () => {
    const state = makeState({ flags: { schedule_rad: true, ihb_heating: true } });
    state.settings.heating_floorheating_pump = "1";   // floor pump commanded on, relay off → DHW priority
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-badges='rad']")?.textContent).toContain("Ночь");
    expect(container.querySelector("[data-badges='floor']")?.textContent).toContain("Приоритет ГВС");
  });

  it("shows autofill lockout", () => {
    const { container } = render(
      <SchemeCanvas state={makeState({ flags: { autofill_fault: true } })} layout="wide" onOpen={() => {}} />,
    );
    expect(container.querySelector("[data-element='autofill'] [data-state='fault']")).not.toBeNull();
  });
});
