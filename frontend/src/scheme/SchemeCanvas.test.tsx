import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { chooseLayout } from "./layouts";
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

