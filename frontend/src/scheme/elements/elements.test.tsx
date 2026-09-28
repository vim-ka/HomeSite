import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FillValve, MixingValve, Pipe, Pump, ValueTag } from ".";

const svg = (el: React.ReactNode) => render(<svg>{el}</svg>);

describe("scheme elements", () => {
  it("pump shows running vs stopped", () => {
    const { container, rerender } = svg(<Pump x={10} y={10} running />);
    expect(container.querySelector("[data-state='running']")).not.toBeNull();
    rerender(<svg><Pump x={10} y={10} running={false} /></svg>);
    expect(container.querySelector("[data-state='stopped']")).not.toBeNull();
  });

  it("mixing valve shows the pulse direction", () => {
    const { container } = svg(<MixingValve x={0} y={0} direction="open" />);
    expect(container.querySelector("[data-state='open']")).not.toBeNull();
  });

  it("fill valve fault state", () => {
    const { container } = svg(<FillValve x={0} y={0} state="fault" />);
    expect(container.querySelector("[data-state='fault']")).not.toBeNull();
  });

  it("value tag shows the value, target and a dash when stale", () => {
    const { rerender } = svg(
      <ValueTag x={0} y={0} unit="°" reading={{ value: 54.12, ts: null, stale: false }} target={54} />,
    );
    expect(screen.getByText("54.1°")).toBeInTheDocument();
    expect(screen.getByText("/54")).toBeInTheDocument();
    rerender(<svg><ValueTag x={0} y={0} unit="°" reading={{ value: 54.12, ts: null, stale: true }} /></svg>);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("pump is a solid disc: green when running, grey when stopped, no dark frame", () => {
    const { container, rerender } = svg(<Pump x={0} y={0} running />);
    const disc = () => container.querySelector("[data-part='disc']")!;
    expect(disc().getAttribute("fill")).toBe("#16a34a");
    expect(disc().getAttribute("stroke")).toBeNull();
    expect(disc().getAttribute("r")).toBe("11");
    rerender(<svg><Pump x={0} y={0} running={false} /></svg>);
    expect(disc().getAttribute("fill")).toBe("#9ca3af");
  });

  it("pump blinks grey/green while switching", () => {
    const { container } = svg(<Pump x={0} y={0} running={false} switching />);
    expect(container.querySelector("[data-part='disc']")!.getAttribute("class")).toContain("scheme-pump-switching");
  });

  it("pipes have flat ends (no round tails poking out of devices)", () => {
    const { container } = svg(<Pipe points={[[0, 0], [10, 0], [10, 10]]} color="#f00" flowing />);
    for (const path of container.querySelectorAll("path")) {
      expect(path.getAttribute("stroke-linecap")).toBe("butt");
    }
  });
});

