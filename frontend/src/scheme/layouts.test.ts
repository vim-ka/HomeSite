import { describe, expect, it } from "vitest";
import { BASE_LAYOUTS, LAYOUTS, mirrorLayout } from "./layouts";

describe("mirrorLayout", () => {
  const base = BASE_LAYOUTS.wide;
  const m = mirrorLayout(base);

  it("mirrors pipe points and point elements around the vertical centre line", () => {
    expect(m.pipes[0]!.points[0]).toEqual([base.width - base.pipes[0]!.points[0]![0], base.pipes[0]!.points[0]![1]]);
    expect(m.radPump).toEqual([base.width - base.radPump[0], base.radPump[1]]);
  });

  it("keeps boxes inside: the right edge becomes the left edge", () => {
    expect(m.boiler).toEqual([base.width - base.boiler[0] - 120, base.boiler[1]]);
    expect(m.radiators).toEqual([base.width - base.radiators[0] - 260, base.radiators[1]]);
    expect(m.tank).toEqual([base.width - base.tank[0] - 80, base.tank[1]]);
  });

  it("anchors text at the mirrored start so it reads left-to-right", () => {
    expect(m.mirrored).toBe(true);
    expect(m.labels[0]!.at).toEqual([base.width - base.labels[0]!.at[0], base.labels[0]!.at[1]]);
  });

  it("is what the scheme uses", () => {
    expect(LAYOUTS.wide).toEqual(mirrorLayout(BASE_LAYOUTS.wide));
    expect(LAYOUTS.tall).toEqual(mirrorLayout(BASE_LAYOUTS.tall));
  });
});

describe("radiator flow direction", () => {
  // Flow animates in point order: every radiator must be fed on its supply port and drained on its return port
  for (const name of ["wide", "tall"] as const) {
    it(`${name}: supply pipes end at radiator ports, return pipes start at them`, () => {
      const L = BASE_LAYOUTS[name];
      const bottom = L.radiators[1] + 46;
      const ports = [0, 95, 190].map((dx) => L.radiators[0] + dx);
      const supply = L.pipes.filter((p) => p.role === "rad_supply");
      const ret = L.pipes.filter((p) => p.role === "rad_return");
      for (const x of ports) {
        expect(supply.some((p) => p.points.at(-1)![0] === x + 8 && p.points.at(-1)![1] === bottom)).toBe(true);
        expect(supply.some((p) => p.points[0]![0] === x + 8 && p.points[0]![1] === bottom)).toBe(false);
        expect(ret.some((p) => p.points[0]![0] === x + 62 && p.points[0]![1] === bottom)).toBe(true);
        expect(ret.some((p) => p.points.at(-1)![0] === x + 62 && p.points.at(-1)![1] === bottom)).toBe(false);
      }
    });
  }

  it("the scheme is centred on the right edge of the pressure gauge (user's reference point)", () => {
    const gaugeRightEdge = LAYOUTS.wide.gauge[0] + 18;
    expect(Math.abs(gaugeRightEdge - 500)).toBeLessThanOrEqual(10);
  });

  it("the tank connection is long enough to fit the loading pump comfortably", () => {
    const L = BASE_LAYOUTS.wide;
    const collectorEnd = L.separator[0] + 36 + 200;
    expect(L.tank[0] - collectorEnd).toBeGreaterThanOrEqual(90);
  });
});
