import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { chooseLayout, LAYOUTS } from "./layouts";
import { SchemeCanvas } from "./SchemeCanvas";
import { makeState } from "./testing";

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

  it("shows night and DHW priority badges; priority sits right beside the pump it holds off", () => {
    const state = makeState({ flags: { schedule_rad: true, ihb_heating: true } });
    state.controller.relays.ihb_pump = true;
    state.settings.heating_floorheating_off_ihb = "1";
    for (const layout of ["wide", "tall"] as const) {
      const { container, unmount } = render(<SchemeCanvas state={state} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-badges='rad']")?.textContent).toContain("Ночь");
      expect(container.querySelector("[data-badges='rad_priority']")).toBeNull();
      const badge = container.querySelector("[data-badges='floor_priority']")!;
      expect(badge.textContent).toBe("Приоритет ГВС");
      const L = LAYOUTS[layout];
      expect(Number(badge.getAttribute("x"))).toBeLessThan(L.floorPump[0]);           // to its left on screen
      expect(L.floorPump[0] - Number(badge.getAttribute("x"))).toBeLessThanOrEqual(25);
      expect(Math.abs(Number(badge.getAttribute("y")) - L.floorPump[1])).toBeLessThanOrEqual(6);
      // the badge (≈ 90 wide, 13 tall, right-anchored) must not run into a value tag or a label
      for (const [k, py] of [["rad", L.radPump[1]], ["floor", L.floorPump[1]]] as const) {
        const bx1 = (k === "rad" ? L.radPump[0] : L.floorPump[0]) - 16, bx0 = bx1 - 90, by1 = py + 4, by0 = by1 - 11;
        for (const [role, [tx, ty]] of Object.entries(L.tags)) {
          const hit = tx > bx0 && tx - 90 < bx1 && ty < by1 && ty + 20 > by0;
          expect(hit, `${k} priority badge vs ${role} tag`).toBe(false);
        }
        for (const l of L.labels) {
          const hit = l.at[0] > bx0 && l.at[0] - 60 < bx1 && l.at[1] - 10 < by1 && l.at[1] > by0;
          expect(hit, `${k} priority badge vs label ${l.text}`).toBe(false);
        }
      }
      unmount();
    }
  });

  it("shows autofill lockout", () => {
    const { container } = render(
      <SchemeCanvas state={makeState({ flags: { autofill_fault: true } })} layout="wide" onOpen={() => {}} />,
    );
    expect(container.querySelector("[data-element='autofill'] [data-state='fault']")).not.toBeNull();
  });
});

describe("SchemeCanvas clicks", () => {
  it("left click on a pump toggles it, right click opens its settings", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    const pump = container.querySelector("[data-element='rad_pump']")!;
    fireEvent.click(pump);
    expect(onToggle).toHaveBeenCalledWith("heating_radiator_pump", "Насос радиаторов", "0");
    expect(onOpen).not.toHaveBeenCalled();
    fireEvent.contextMenu(pump);
    expect(onOpen).toHaveBeenCalledWith("rad", undefined);
  });

  it("a touch tap opens settings instead of toggling", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    const pump = container.querySelector("[data-element='rad_pump']")!;
    fireEvent.pointerDown(pump, { pointerType: "touch" });
    fireEvent.click(pump);
    expect(onToggle).not.toHaveBeenCalled();
    expect(onOpen).toHaveBeenCalledWith("rad", undefined);
  });

  it("elements without an on/off open settings on left click", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    fireEvent.click(container.querySelector("[data-element='tank']")!);
    expect(onToggle).not.toHaveBeenCalled();
    expect(onOpen).toHaveBeenCalledWith("tank", undefined);
  });
});

describe("SchemeCanvas water supply", () => {
  for (const layout of ["wide", "tall"] as const) {
    it(`${layout}: well with the cold water pump, recirculation pump on the return loop`, () => {
      const { container } = render(<SchemeCanvas state={makeState()} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='well']")).not.toBeNull();
      expect(container.querySelector("[data-element='cold_pump']")).not.toBeNull();
      expect(container.querySelector("[data-pipe='recirc_return']")).not.toBeNull();
      expect(container.querySelector("[data-pipe='cold_to_tank']")).not.toBeNull();
      expect(container.querySelector("[data-pipe='cold_to_fill']")).not.toBeNull();
    });
  }
});

describe("SchemeCanvas on/off state", () => {
  it("shows when autofill or a pump is switched off in the settings, and names the click action", () => {
    const state = makeState();
    state.settings.heating_autofill_enabled = "0";
    state.settings.heating_radiator_pump = "1";
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} onToggle={() => {}} />);
    const fill = container.querySelector("[data-element='autofill']")!;
    expect(fill.getAttribute("data-enabled")).toBe("false");
    expect(fill.querySelector("title")?.textContent).toMatch(/клик — включить/i);
    const pump = container.querySelector("[data-element='rad_pump']")!;
    expect(pump.getAttribute("data-enabled")).toBe("true");
    expect(pump.querySelector("title")?.textContent).toMatch(/клик — выключить/i);
  });

  it("toggles by the relay when the setting is unknown", () => {
    const onToggle = vi.fn();
    const state = makeState();
    delete state.settings.heating_radiator_pump;   // relay rad_pump is on in the fixture
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} onToggle={onToggle} />);
    expect(container.querySelector("[data-element='rad_pump'] title")?.textContent).toMatch(/клик — выключить/i);
  });
});

describe("SchemeCanvas water colours", () => {
  it("collector bars and separator gradient follow the boiler supply/return temperatures", async () => {
    const { pipeColor } = await import("./pipeColor");
    const state = makeState();
    state.values.boiler_supply = { value: 70, ts: "2026-01-20T12:00:00Z", stale: false };
    state.values.boiler_return = { value: 40, ts: "2026-01-20T12:00:00Z", stale: false };
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    const sep = container.querySelector("[data-element='separator']")!;
    expect(sep.querySelector("[data-bar='supply']")?.getAttribute("fill")).toBe(pipeColor(70, "supply"));
    expect(sep.querySelector("[data-bar='return']")?.getAttribute("fill")).toBe(pipeColor(40, "return"));
    const stops = [...sep.querySelectorAll("stop")].map((s) => s.getAttribute("stop-color"));
    expect(stops[0]).toBe(pipeColor(70, "supply"));
    expect(stops.at(-1)).toBe(pipeColor(40, "return"));
  });
});

describe("SchemeCanvas accessibility and input", () => {
  it("is a labelled group of Russian-named buttons", () => {
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={() => {}} />);
    expect(screen.getByRole("group", { name: "Схема котельной" })).toBeInTheDocument();
    expect(container.querySelector("[data-element='rad_pump']")?.getAttribute("aria-label")).toBe("Насос радиаторов");
    expect(container.querySelector("[data-element='radiators']")?.getAttribute("aria-label")).toBe("Радиаторы");
  });

  it("a stylus tap opens settings instead of toggling", () => {
    const onOpen = vi.fn();
    const onToggle = vi.fn();
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={onOpen} onToggle={onToggle} />);
    const pump = container.querySelector("[data-element='rad_pump']")!;
    fireEvent.pointerDown(pump, { pointerType: "pen" });
    fireEvent.click(pump);
    expect(onToggle).not.toHaveBeenCalled();
    expect(onOpen).toHaveBeenCalled();
  });
});

describe("SchemeCanvas pumps", () => {
  const PUMPS = ["rad_pump", "floor_pump", "ihb_pump", "recirc_pump", "cold_pump"];

  it("all pumps have the same size", () => {
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={() => {}} />);
    const radii = PUMPS.map((id) => container.querySelector(`[data-element='${id}'] [data-part='disc']`)?.getAttribute("r"));
    expect(new Set(radii)).toEqual(new Set(["11"]));
  });

  it("a pump switched off in the settings is plain grey, not see-through", () => {
    const state = makeState();
    state.settings.heating_radiator_pump = "0";
    state.controller.relays.rad_pump = false;
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} onToggle={() => {}} />);
    const el = container.querySelector("[data-element='rad_pump']")!;
    expect(el.getAttribute("opacity")).toBeNull();
    expect(el.querySelector("[data-part='disc']")!.getAttribute("fill")).toBe("#9ca3af");
  });

  it("blinks while its command is pending or being sent", () => {
    const state = makeState();
    state.sync.pending = ["heating_floorheating_pump"];
    const { container } = render(
      <SchemeCanvas state={state} layout="wide" onOpen={() => {}} busyKeys={["heating_radiator_pump"]} />,
    );
    expect(container.querySelector("[data-element='floor_pump'] .scheme-pump-switching")).not.toBeNull();
    expect(container.querySelector("[data-element='rad_pump'] .scheme-pump-switching")).not.toBeNull();
    expect(container.querySelector("[data-element='ihb_pump'] .scheme-pump-switching")).toBeNull();
  });
});


describe("SchemeCanvas taps and TEH", () => {
  it("hot tap is labelled ГВС with red streams, cold tap ХВС with blue ones", () => {
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={() => {}} />);
    const hot = container.querySelector("[data-element='tap']")!;
    const cold = container.querySelector("[data-element='cold_tap']")!;
    expect(hot.textContent).toContain("ГВС");
    expect(cold.textContent).toContain("ХВС");
    expect(hot.querySelector("[data-part='streams']")!.getAttribute("stroke")).toBe("#ef4444");
    expect(cold.querySelector("[data-part='streams']")!.getAttribute("stroke")).toBe("#0ea5e9");
  });

  it("TEH in the tank: left click switches it, glows when on, blinks while switching", () => {
    const state = makeState();
    state.settings.watersupply_ihb_teh_power = "0";
    state.controller.relays.teh = false;
    const onToggle = vi.fn();
    const { container, rerender } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} onToggle={onToggle} />);
    const teh = container.querySelector("[data-element='teh']")!;
    expect(teh.querySelector("[data-state='off']")).not.toBeNull();
    fireEvent.pointerDown(teh, { pointerType: "mouse" });
    fireEvent.click(teh);
    expect(onToggle).toHaveBeenCalledWith("watersupply_ihb_teh_power", "ТЭН", "1");

    const on = makeState();
    on.controller.relays.teh = true;
    on.sync.pending = ["watersupply_ihb_teh_power"];
    rerender(<SchemeCanvas state={on} layout="wide" onOpen={() => {}} onToggle={onToggle} />);
    expect(container.querySelector("[data-element='teh'] [data-state='on']")).not.toBeNull();
    expect(container.querySelector("[data-element='teh'] .scheme-teh-switching")).not.toBeNull();
  });
});

describe("SchemeCanvas enabled vs working", () => {
  it("boiler in auto with the burner paused: green dot, no flame, tooltip says it's waiting", () => {
    const state = makeState();
    state.settings.heating_boiler_automode = "1";
    state.controller.relays.boiler = false;
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} onToggle={() => {}} />);
    const boiler = container.querySelector("[data-element='boiler']")!;
    expect(boiler.querySelector("[data-part='led']")!.getAttribute("fill")).toBe("#22c55e");
    expect(boiler.querySelector("[data-part='flame']")).toBeNull();
    expect(boiler.querySelector("title")!.textContent).toMatch(/авто-режим, сейчас в ожидании/);
  });

  it("boiler switched off by hand: grey dot", () => {
    const state = makeState();
    state.settings.heating_boiler_automode = "0";
    state.settings.heating_boiler_power = "0";
    state.controller.relays.boiler = false;
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    expect(container.querySelector("[data-element='boiler'] [data-part='led']")!.getAttribute("fill")).not.toBe("#22c55e");
  });

  it("TEH switched on but held off by the controller: orange, no heat waves; heating: heat waves", () => {
    const state = makeState();
    state.settings.watersupply_ihb_teh_power = "1";
    state.controller.relays.teh = false;
    const { container, rerender } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    const teh = () => container.querySelector("[data-element='teh']")!;
    expect(teh().querySelector("[data-state='standby']")).not.toBeNull();
    expect(teh().querySelector("[data-part='element']")!.getAttribute("stroke")).toBe("#f97316");
    expect(teh().querySelector("[data-part='heat']")).toBeNull();

    const heating = makeState();
    heating.settings.watersupply_ihb_teh_power = "1";
    heating.controller.relays.teh = true;
    rerender(<SchemeCanvas state={heating} layout="wide" onOpen={() => {}} />);
    expect(teh().querySelector("[data-state='on'] [data-part='heat']")).not.toBeNull();
  });
});

describe("SchemeCanvas mixing valves", () => {
  it("valves face their flow: radiators out upwards, floor out downwards, third port towards the bypass", () => {
    const { container } = render(<SchemeCanvas state={makeState()} layout="wide" onOpen={() => {}} />);
    const rad = container.querySelector("[data-element='rad_valve'] [data-out]")!;
    const floor = container.querySelector("[data-element='floor_valve'] [data-out]")!;
    expect(rad.getAttribute("data-out")).toBe("up");
    expect(floor.getAttribute("data-out")).toBe("down");
    // mirrored layout: the return riser (bypass) is on the valves' right on screen
    expect(rad.getAttribute("data-bypass")).toBe("right");
    expect(floor.getAttribute("data-bypass")).toBe("right");
  });

  it("TEH heating: heat waves float up", () => {
    const state = makeState();
    state.controller.relays.teh = true;
    const { container } = render(<SchemeCanvas state={state} layout="wide" onOpen={() => {}} />);
    expect(container.querySelectorAll("[data-element='teh'] [data-part='heat'] .scheme-heat").length).toBe(2);
  });
});

describe("SchemeCanvas manual-mode hints", () => {
  it("marks the element with an amber sign whose tooltip explains the hint", () => {
    const state = makeState();
    state.settings.watersupply_ihb_automode = "0";
    state.controller.relays.ihb_pump = true;
    state.controller.targets.ihb = 65;
    state.values.tank = { value: 67, ts: "2026-01-20T12:00:00Z", stale: false };
    for (const layout of ["wide", "tall"] as const) {
      const { container, unmount } = render(<SchemeCanvas state={state} layout={layout} onOpen={() => {}} />);
      const mark = container.querySelector("[data-hint='ihb_pump']")!;
      expect(mark.querySelector("title")!.textContent).toMatch(/уже нагрет/);
      expect(container.querySelector("[data-hint='boiler']")).toBeNull();
      unmount();
    }
  });
});

describe("SchemeCanvas autofill mode", () => {
  it("says 'авто' at the valve when autofill is on and 'выкл' when it is off", () => {
    for (const layout of ["wide", "tall"] as const) {
      const state = makeState();
      state.settings.heating_autofill_enabled = "1";
      const { container, unmount, rerender } = render(<SchemeCanvas state={state} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='autofill'] [data-part='caption']")!.textContent).toBe("авто");
      const off = makeState();
      off.settings.heating_autofill_enabled = "0";
      rerender(<SchemeCanvas state={off} layout={layout} onOpen={() => {}} />);
      expect(container.querySelector("[data-element='autofill'] [data-part='caption']")!.textContent).toBe("выкл");
      unmount();
    }
  });
});
