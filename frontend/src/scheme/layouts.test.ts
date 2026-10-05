import { describe, expect, it } from "vitest";
import { BASE_LAYOUTS, LAYOUTS, mirrorLayout, type LayoutDef } from "./layouts";
import { PIPE_HALF, deltaBox, elementBoxes, instrumentBoxes, legHits, onPipe, overlaps, pipeBoxes, tagLeg } from "./geometry";
import type { RoleKey } from "./types";

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

  it("wide: the circuit risers sit in the middle of the collector", () => {
    const L = BASE_LAYOUTS.wide;
    const collectorMid = L.separator[0] + 36 + (L.collectorWidth ?? 200) / 2;
    const returnRiser = L.pipes.find((p) => p.id === "rad_bypass")!.points[0]![0];
    expect(Math.abs((L.radPump[0] + returnRiser) / 2 - collectorMid)).toBeLessThanOrEqual(5);
    expect(L.floorPump[0]).toBe(L.radPump[0]);
  });

  it("the tank connection is long enough to fit the loading pump comfortably", () => {
    const L = BASE_LAYOUTS.wide;
    const collectorEnd = L.separator[0] + 36 + 200;
    expect(L.tank[0] - collectorEnd).toBeGreaterThanOrEqual(90);
  });
});

describe("value tags", () => {
  // where each sensor is mounted (Настройки → точки монтажа): the loading supply (tsihb_s, «БКН, подача») on the
  // loading pipe; the tank (tswatersupply_h, regulated on) in its upper sleeve, shown with a callout;
  // heating pressure (prs_heating) on the boiler return; the well water sensors (tswatersupply_c, prs_water)
  // on the main right after the well pump
  const source = (L: LayoutDef, role: RoleKey, [x, y]: [number, number]): boolean => {
    const pin: [number, number] = [x, y];
    if (role === "coil_supply") return !L.tags.coil_supply!.dial && onPipe(L, pin, (p) => p.id === "ihb_feed");
    if (role === "tank") {
      const s = L.tankScale ?? 1;
      const [x0, y0] = L.tank, [x1, y1] = [x0 + 80 * s, y0 + 190 * s];
      return !!L.tags.tank!.dial && x > x0 + 10 * s && x < x1 - 10 * s && y > y0 + 20 * s && y < (y0 + y1) / 2;
    }
    if (role === "heating_pressure") return onPipe(L, pin, (p) => p.role === "boiler_return");
    if (role === "cold_water" || role === "water_pressure") {
      // the stretch of the well pipe from the pump on (water flows in point order), clear of the pump's disc
      const well = L.pipes.find((p) => p.id === "cold_from_well")!;
      const seg = well.points.findIndex((a, i) => {
        const q = well.points[i + 1];
        return !!q && onPipe({ ...L, pipes: [{ ...well, points: [a, q] }] }, L.coldPump, () => true);
      });
      const afterPump = { ...well, points: [L.coldPump, ...well.points.slice(seg + 1)] };
      const clearOfPump = Math.hypot(pin[0] - L.coldPump[0], pin[1] - L.coldPump[1]) >= 11 + PIPE_HALF;
      return clearOfPump && onPipe({ ...L, pipes: [afterPump] }, pin, () => true);
    }
    return onPipe(L, pin, (p) => p.role === role);
  };

  for (const name of ["wide", "tall"] as const) {
    const L = LAYOUTS[name];
    const roles = Object.keys(L.tags) as RoleKey[];

    it(`${name}: every instrument's stem ends on what the reading is measured on`, () => {
      for (const role of roles) expect(source(L, role, L.tags[role]!.pin), role).toBe(true);
    });

    it(`${name}: dials and tags sit clear of pipes, devices, captions, the panel and each other`, () => {
      const others = [...elementBoxes(L), ...pipeBoxes(L)];
      for (const role of roles) {
        for (const b of instrumentBoxes(L, role)) {
          expect(b.x0 >= 0 && b.y0 >= 0 && b.x1 <= L.width && b.y1 <= L.height, `${b.what} inside the scheme`).toBe(true);
          for (const o of others) expect(overlaps(b, o, 2), `${b.what} runs into ${o.what}`).toBe(false);
          for (const r2 of roles) {
            if (r2 === role) continue;
            for (const o of instrumentBoxes(L, r2)) expect(overlaps(b, o, 4), `${b.what} runs into ${o.what}`).toBe(false);
          }
        }
      }
    });

    it(`${name}: a reading sits next to its dial, never back towards the pipe`, () => {
      const back = { left: "right", right: "left", up: "down", down: "up" } as const;
      for (const role of roles) {
        const t = L.tags[role]!;
        expect(t.tag, role).not.toBe(back[t.side]);
      }
    });

    it(`${name}: stems are visible and cross nothing on the way to their pipe`, () => {
      const others = [...elementBoxes(L), ...pipeBoxes(L), ...roles.flatMap((r) => instrumentBoxes(L, r))];
      for (const role of roles) {
        const t = L.tags[role]!;
        const leg = tagLeg(t);
        const length = Math.hypot(leg[0][0] - leg[1][0], leg[0][1] - leg[1][1]);
        expect(length, `${role} stem`).toBeGreaterThanOrEqual(6);
        // the stem stops at the pipe's edge (the tank wall) and never lies on the pipe
        if (!t.dial) {
          const [dx, dy] = [Math.sign(leg[0][0] - leg[1][0]), Math.sign(leg[0][1] - leg[1][1])];
          const off = t.wall ? 0 : PIPE_HALF;
          expect(leg[1], `${role} stem foot`).toEqual([t.pin[0] + dx * off, t.pin[1] + dy * off]);
          expect(length, `${role} stem keeps its length`).toBe(t.len);
        }
        const [px, py] = t.pin;
        for (const o of others) {
          const own = o.what === `tag ${role}` || o.what === `dial ${role}` || (o.x0 <= px && px <= o.x1 && o.y0 <= py && py <= o.y1);
          if (!own) expect(legHits(leg, o), `${role} leg crosses ${o.what}`).toBe(false);
        }
      }
    });
  }
});

describe("mixing units", () => {
  for (const name of ["wide", "tall"] as const) {
    for (const c of ["rad", "floor"] as const) {
      it(`${name} ${c}: collector → 3-way valve → pump, colours change at the valve`, () => {
        const L = BASE_LAYOUTS[name];
        const valve = c === "rad" ? L.radValve : L.floorValve;
        const pump = c === "rad" ? L.radPump : L.floorPump;
        const role = c === "rad" ? "rad_supply" : "floor_supply";
        // hot water from the collector reaches the valve…
        const feed = L.pipes.find((p) => p.id === `${c}_feed`)!;
        expect(feed.role).toBe("boiler_supply");
        expect(feed.points.at(-1)).toEqual(valve);
        // …mixed water leaves it, and the pump comes after the valve
        const mixed = L.pipes.find((p) => p.id === `${c}_mixed`)!;
        expect(mixed.role).toBe(role);
        expect(mixed.points[0]).toEqual(valve);
        const along = (pt: [number, number]) => Math.abs(pt[1] - feed.points[0]![1]);
        expect(along(pump)).toBeGreaterThan(along(valve));
        // bypass from the circuit return into the valve's third port
        const bypass = L.pipes.find((p) => p.id === `${c}_bypass`)!;
        expect(bypass.role).toBe(c === "rad" ? "rad_return" : "floor_return");
        expect(Math.abs(bypass.points.at(-1)![1] - valve[1])).toBeLessThanOrEqual(1);
      });
    }
  }

  it("wide: the pipe from the collector down to the floor loops is long enough for valve + pump", () => {
    const L = BASE_LAYOUTS.wide;
    const feed = L.pipes.find((p) => p.id === "floor_feed")!;
    const mixed = L.pipes.find((p) => p.id === "floor_mixed")!;
    expect(mixed.points.at(-1)![1] - feed.points[0]![1]).toBeGreaterThanOrEqual(200);
  });
});

describe("DHW tank", () => {
  for (const name of ["wide", "tall"] as const) {
    it(`${name}: pipes meet the tank outline and never stick into it`, () => {
      const L = BASE_LAYOUTS[name];
      const s = L.tankScale ?? 1;
      const [x0, y0] = L.tank;
      const [x1, y1] = [x0 + 80 * s, y0 + 190 * s];
      for (const p of L.pipes) {
        for (const [x, y] of [p.points[0]!, p.points.at(-1)!]) {
          const inside = x > x0 && x < x1 && y > y0 && y < y1;
          expect(inside, `${p.id ?? p.role} ends inside the tank at ${x},${y}`).toBe(false);
        }
      }
    });
  }

  it("wide: the recirculation loop is centred on the tank height, its pump close to the tank", () => {
    const L = BASE_LAYOUTS.wide;
    const loop = L.pipes.find((p) => p.id === "recirc_return")!;
    const top = L.pipes.find((p) => p.id === "hot_to_tap")!.points[0]![1];
    const bottom = loop.points.at(-1)![1];
    expect((top + bottom) / 2).toBe(L.tank[1] + 95);
    expect(L.recircPump[1]).toBe(bottom);
    expect(L.recircPump[0] - (L.tank[0] + 80)).toBeLessThanOrEqual(40);
  });

  it.each(["wide", "tall"] as const)("%s: cold water rises from the main to its own tap", (name) => {
    const L = BASE_LAYOUTS[name];
    const pipe = L.pipes.find((p) => p.id === "cold_to_tap")!;
    const toTank = L.pipes.find((p) => p.id === "cold_to_tank")!;
    expect(toTank.points.some(([x, y]) => x === pipe.points[0]![0] && y === pipe.points[0]![1])).toBe(true);
    expect(pipe.points.at(-1)).toEqual([L.coldTap![0] + 12, L.coldTap![1] + 26]);
  });
});

describe("pumps and valves mounted on the collector", () => {
  it.each(["wide", "tall"] as const)("%s: mixing units and the tank loading pump sit right at the collector", (name) => {
    const L = BASE_LAYOUTS[name];
    const [sx, sy] = L.separator;
    const supplyTop = sy + 15, returnBottom = sy + 125;
    const collectorEnd = sx + 36 + (L.collectorWidth ?? 200);
    expect(supplyTop - L.radValve[1]).toBeLessThanOrEqual(14);
    expect(L.floorValve[1] - returnBottom).toBeLessThanOrEqual(14);
    expect(L.radValve[1] - L.radPump[1]).toBeLessThanOrEqual(35);
    expect(L.floorPump[1] - L.floorValve[1]).toBeLessThanOrEqual(35);
    expect(L.ihbPump[0] - collectorEnd).toBeLessThanOrEqual(16);
  });
});

describe("radiators label", () => {
  it("wide: 'Радиаторы' sits left of the radiators on screen, the scheme starts near the top", () => {
    const L = LAYOUTS.wide;
    const label = L.labels.find((l) => l.text === "Радиаторы")!;
    expect(label.align).toBeUndefined();                 // right-anchored in the mirrored layout
    expect(label.at[0]).toBeLessThanOrEqual(L.radiators[0] - 8);
    expect(label.at[1]).toBeGreaterThan(L.radiators[1]);
    expect(label.at[1]).toBeLessThan(L.radiators[1] + 46);
    expect(L.radiators[1]).toBeLessThanOrEqual(16);
  });
});

describe("message panel area", () => {
  it("wide: a free box top right — right of the radiators, above the boiler, clear of labels", () => {
    const L = LAYOUTS.wide;
    const p = L.panel!;
    const [x0, x1, y1] = [p.at[0], p.at[0] + p.width, p.at[1] + p.height];
    expect(x1).toBeLessThanOrEqual(L.width);
    expect(x0).toBeGreaterThanOrEqual(L.radiators[0] + 260 + 8);
    expect(y1).toBeLessThanOrEqual(L.boiler[1] - 6);
    expect(y1).toBeLessThanOrEqual(L.separator[1] - 20);   // separator air vent
    expect(p.width).toBeGreaterThanOrEqual(280);
    for (const l of L.labels) expect(l.at[0] > x0 && l.at[1] < y1 + 12, `label ${l.text}`).toBe(false);
  });

  it("tall: no room — the panel stays below the scheme", () => {
    expect(LAYOUTS.tall.panel).toBeUndefined();
  });
});

describe("well", () => {
  it.each(["wide", "tall"] as const)("%s: the pipe drops into the wellhead from above (Г-shaped), the well fits the scheme", (name) => {
    const L = BASE_LAYOUTS[name];
    const [a, b, c] = L.pipes.find((p) => p.id === "cold_from_well")!.points;
    expect(a).toEqual([L.well[0] + 25, L.well[1] + 2]);   // top of the wellhead, over the casing
    expect(b![0]).toBe(a![0]);                               // straight up first…
    expect(a![1] - b![1]).toBeGreaterThanOrEqual(16);
    expect(c![1]).toBe(b![1]);                               // …then along to the pump
    expect(L.well[1] + 80).toBeLessThanOrEqual(L.height);
  });
});

describe("circuit differences", () => {
  it.each(["wide", "tall"] as const)("%s: the ΔT labels sit clear of everything", (name) => {
    const L = LAYOUTS[name];
    const others = [...elementBoxes(L), ...pipeBoxes(L), ...(Object.keys(L.tags) as RoleKey[]).flatMap((r) => instrumentBoxes(L, r))];
    for (const k of ["rad", "floor", "coil"] as const) {
      const b = deltaBox(L.deltas[k], `${k} delta`);
      expect(b.x0 >= 0 && b.x1 <= L.width && b.y0 >= 0 && b.y1 <= L.height, `${k} inside`).toBe(true);
      for (const o of others) if (o.what !== `${k} delta`) expect(overlaps(b, o, 2), `${k} ΔT runs into ${o.what}`).toBe(false);
    }
  });
});
