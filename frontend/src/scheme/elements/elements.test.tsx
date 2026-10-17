import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { FillValve, MixingValve, Pipe, Pump, ValueTag } from ".";
import { Dial } from "./ValueTag";
import { Tank, coilPath } from "./Tank";

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
    const tag = { pin: [100, 50] as [number, number], side: "right" as const, len: 8 };
    const { rerender } = svg(
      <ValueTag tag={tag} unit="°" reading={{ value: 54.12, ts: null, stale: false }} target={54} />,
    );
    expect(screen.getByText("/54°").textContent).toBe("/54°");
    expect(screen.getByText("/54°").parentElement!.textContent).toBe("54.1°/54°");   // no gap, degree on the target
    rerender(<svg><ValueTag tag={tag} unit="°" reading={{ value: 54.12, ts: null, stale: true }} /></svg>);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("value tag is a dial on a stem from the pipe, the reading next to the dial", () => {
    const { container } = svg(
      <ValueTag tag={{ pin: [100, 50], side: "left", len: 8 }} unit="°" reading={{ value: 54.12, ts: null, stale: false }} />,
    );
    const stem = container.querySelector("[data-part='stem']")!;
    expect([stem.getAttribute("x1"), stem.getAttribute("y1"), stem.getAttribute("x2"), stem.getAttribute("y2")])
      .toEqual(["89", "50", "97", "50"]);   // 8 long, from the pipe's edge (pipe centre 100, half width 3)
    // dial centre: pipe edge + 8 of stem + its 12 radius
    const dial = container.querySelector("[data-part='dial']")!;
    expect(dial.getAttribute("transform")).toBe("translate(77 50)");
    expect(dial.getAttribute("data-kind")).toBe("temp");
    expect(container.querySelector("[data-part='needle']")).not.toBeNull();
    // the reading sits 3 past the dial, further from the pipe
    expect(container.querySelector("g[transform^='translate(1'], g[transform^='translate(2']")!.getAttribute("transform")).toBe(`translate(${77 - 12 - 3 - (12 + 5 * 7)} 40)`);
  });

  it("manometer with a working range: green inside it, red outside", () => {
    const { container } = svg(<Dial x={0} y={0} value={1.2} min={0} max={4} kind="pressure" lo={1} hi={1.8} />);
    expect(container.querySelectorAll("[data-zone='ok']")).toHaveLength(1);
    expect(container.querySelectorAll("[data-zone='bad']")).toHaveLength(2);
    const plain = svg(<Dial x={0} y={0} value={1.2} min={0} max={4} kind="pressure" />);
    expect(plain.container.querySelector("[data-zone]")).toBeNull();
  });

  it("stale reading: dial without a needle", () => {
    const { container } = svg(
      <ValueTag tag={{ pin: [100, 50], side: "up" }} unit=" бар" reading={{ value: 3, ts: null, stale: true }} />,
    );
    expect(container.querySelector("[data-part='dial']")!.getAttribute("data-kind")).toBe("pressure");
    expect(container.querySelector("[data-part='needle']")).toBeNull();
  });

  it("tank coil runs from the inlet down to the outlet; water moves through it only while loading", () => {
    const coil = { side: "right" as const, inY: 50, outY: 130, supplyColor: "#f00", returnColor: "#00f", flowing: false };
    const { all } = coilPath(coil);
    expect(all.startsWith("M80 50 H66")).toBe(true);     // in through the right wall at the feed
    expect(all.endsWith("H80")).toBe(true);              // out through the same wall…
    expect(all).toContain(" 66 130");                    // …at the coil return
    const { container, rerender } = svg(<Tank x={0} y={0} fill={0.5} coil={coil} />);
    expect(container.querySelector("[data-part='coil']")).not.toBeNull();
    expect(container.querySelector("[data-part='coil-flow']")).toBeNull();
    rerender(<svg><Tank x={0} y={0} fill={0.5} coil={{ ...coil, flowing: true }} /></svg>);
    expect(container.querySelector("[data-part='coil-flow']")).not.toBeNull();
  });

  it("tall tank: an outlet below the coil drops along the wall side, clear of the TEH", () => {
    const { all } = coilPath({ side: "right", inY: 33, outY: 167 });
    expect(all.endsWith("V167 H80")).toBe(true);
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

