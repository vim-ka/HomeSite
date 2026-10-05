import type { LayoutDef, TagDef } from "./layouts";
import type { RoleKey } from "./types";

type Pt = [number, number];

/** Axis-aligned box; `what` names the thing it belongs to (for test messages and exclusions). */
export interface Box { x0: number; y0: number; x1: number; y1: number; what: string }

export const TAG_HEIGHT = 20;
const CHAR = 7;  // tag text is 12 px semibold tabular digits

/** Tag width for its text; a target ("/58") adds a fixed tail. */
export function tagWidth(chars: number, target: boolean): number {
  return 12 + chars * CHAR + (target ? 24 : 0);
}

/** Roles whose tag shows the controller's target next to the reading */
export const TARGET_ROLES: RoleKey[] = ["boiler_supply", "rad_supply", "floor_supply", "tank"];
export const PRESSURE_ROLES: RoleKey[] = ["heating_pressure", "water_pressure"];

/** Widest the tag of this role gets ("88.8°" + target, "8.88 бар") — what the layout has to fit. */
export function maxTagWidth(role: RoleKey): number {
  return PRESSURE_ROLES.includes(role) ? tagWidth(8, false) : tagWidth(5, TARGET_ROLES.includes(role));
}

export const DIAL_R = 12;
const TAG_GAP = 3;

const DIR = { right: [1, 0], left: [-1, 0], up: [0, -1], down: [0, 1] } as const;

/** Where the stem meets the pipe: its edge (half a pipe off the centre line), or the device wall itself. */
function stemFoot(t: TagDef): Pt {
  const [dx, dy] = DIR[t.side];
  const off = t.wall ? 0 : PIPE_HALF;
  return [t.pin[0] + dx * off, t.pin[1] + dy * off];
}

/** Centre of the instrument's dial: the stem runs `len` from the pipe's edge, then the dial. */
export function dialAt(t: TagDef): Pt {
  if (t.dial) return t.dial;
  const [dx, dy] = DIR[t.side];
  const [fx, fy] = stemFoot(t);
  const d = (t.len ?? 10) + DIAL_R;
  return [fx + dx * d, fy + dy * d];
}

/**
 * Where the reading goes: right next to the dial, on `tag` (default: further out along the stem);
 * left/right tags are centred on the dial vertically, up/down ones horizontally.
 */
export function tagRect(t: TagDef, width: number): { x: number; y: number; width: number } {
  const [cx, cy] = dialAt(t);
  const off = DIAL_R + TAG_GAP;
  switch (t.tag ?? t.side) {
    case "right": return { x: cx + off, y: cy - TAG_HEIGHT / 2, width };
    case "left": return { x: cx - off - width, y: cy - TAG_HEIGHT / 2, width };
    case "up": return { x: cx - width / 2, y: cy - off - TAG_HEIGHT, width };
    case "down": return { x: cx - width / 2, y: cy + off, width };
  }
}

/** The stem from the dial's rim to the pipe's edge; a callout: from the rim straight to the sensor's point */
export function tagLeg(t: TagDef): [Pt, Pt] {
  if (t.dial) {
    const [[cx, cy], [px, py]] = [t.dial, t.pin];
    const d = Math.hypot(px - cx, py - cy);
    return [[cx + ((px - cx) * DIAL_R) / d, cy + ((py - cy) * DIAL_R) / d], t.pin];
  }
  const [dx, dy] = DIR[t.side];
  const [cx, cy] = dialAt(t);
  return [[cx - dx * DIAL_R, cy - dy * DIAL_R], stemFoot(t)];
}

export function tagBox(L: LayoutDef, role: RoleKey): Box {
  const r = tagRect(L.tags[role]!, maxTagWidth(role));
  return { x0: r.x, y0: r.y, x1: r.x + r.width, y1: r.y + TAG_HEIGHT, what: `tag ${role}` };
}

/** The instrument's dial */
export function dialBox(L: LayoutDef, role: RoleKey): Box {
  const [cx, cy] = dialAt(L.tags[role]!);
  return { x0: cx - DIAL_R, y0: cy - DIAL_R, x1: cx + DIAL_R, y1: cy + DIAL_R, what: `dial ${role}` };
}

/** Everything a reading takes: its tag and its dial */
export function instrumentBoxes(L: LayoutDef, role: RoleKey): Box[] {
  return [tagBox(L, role), dialBox(L, role)];
}

const box = (x0: number, y0: number, x1: number, y1: number, what: string): Box =>
  ({ x0: Math.min(x0, x1), y0: Math.min(y0, y1), x1: Math.max(x0, x1), y1: Math.max(y0, y1), what });
const around = ([x, y]: Pt, r: number, what: string) => box(x - r, y - r, x + r, y + r, what);

/** Text box: bold 12 px Cyrillic ≈ 8 px per char, the 11 px badges ≈ 7; y is the baseline. */
function textBox(text: string, [x, y]: Pt, anchor: "start" | "end" | "middle", what: string, size = 12): Box {
  const w = text.length * size * (size >= 12 ? 0.66 : 0.62);   // the 11 px badges are not bold
  const x0 = anchor === "start" ? x : anchor === "end" ? x - w : x - w / 2;
  return box(x0, y - size, x0 + w, y + 3, what);
}

export const PIPE_HALF = 3;

/** Pipes as thin boxes, one per straight segment */
export function pipeBoxes(L: LayoutDef): (Box & { role?: RoleKey; id?: string })[] {
  return L.pipes.flatMap((p, i) => p.points.slice(1).map((q, j) => {
    const a = p.points[j]!;
    return { ...box(a[0] - PIPE_HALF, a[1] - PIPE_HALF, q[0] + PIPE_HALF, q[1] + PIPE_HALF, `pipe ${p.id ?? p.role ?? i}`),
             role: p.role, id: p.id };
  }));
}

/** Everything drawn on the scheme except pipes and value tags, as boxes (state badges included: they come and go). */
export function elementBoxes(L: LayoutDef): Box[] {
  const bs = L.boilerScale ?? 1, ts = L.tankScale ?? 1, cw = L.collectorWidth ?? 200;
  const end = L.mirrored ? "end" : "start";
  const [sx, sy] = L.separator;
  const barX = L.mirrored ? sx - cw : sx + 36;
  const out: Box[] = [
    box(L.boiler[0], L.boiler[1], L.boiler[0] + 120 * bs, L.boiler[1] + 170 * bs, "boiler"),
    box(sx, sy - 14, sx + 36, sy + 150, "separator"),
    box(barX, sy + 15, barX + cw, sy + 45, "supply collector"),
    box(barX, sy + 95, barX + cw, sy + 125, "return collector"),
    box(L.radiators[0], L.radiators[1], L.radiators[0] + 260, L.radiators[1] + 46, "radiators"),
    box(L.floor[0] - 6, L.floor[1] - 6, L.floor[0] + 166, L.floor[1] + 52, "floor loops"),
    box(L.tank[0], L.tank[1], L.tank[0] + 80 * ts, L.tank[1] + 190 * ts, "tank"),
    box(L.well[0] - 6, L.well[1] + 2, L.well[0] + 56, L.well[1] + 80, "well"),
  ];
  for (const [name, at] of [["tap", L.tap], ["cold tap", L.coldTap]] as const) {
    if (at) out.push(box(at[0] - 2, at[1] - 18, at[0] + 26, at[1] + 24, name));
  }
  for (const [name, at] of Object.entries({ radPump: L.radPump, floorPump: L.floorPump, ihbPump: L.ihbPump,
                                             recircPump: L.recircPump, coldPump: L.coldPump })) {
    out.push(around(at, 11, name));
  }
  // 3-way valves: body + outlet chevron; "откр"/"закр" on the side away from the bypass
  for (const c of ["rad", "floor"] as const) {
    const [vx, vy] = c === "rad" ? L.radValve : L.floorValve;
    const mixed = L.pipes.find((p) => p.id === `${c}_mixed`)!.points.at(-1)!;
    const bypass = L.pipes.find((p) => p.id === `${c}_bypass`)!.points[0]!;
    const o = mixed[1] < vy ? -1 : 1, b = bypass[0] < vx ? -1 : 1;
    out.push(box(vx - 10, vy - 10 * o, vx + 10, vy + 19 * o, `${c} valve`));
    out.push(box(vx - 12 * b, vy - 6, vx - 36 * b, vy + 5, `${c} valve caption`));
    // "Приоритет ГВС" beside the circuit pump
    const [px, py] = c === "rad" ? L.radPump : L.floorPump;
    out.push(textBox("Приоритет ГВС", [L.mirrored ? px - 16 : px + 16, py + 4], end, `${c} priority badge`, 11));
  }
  // autofill valve with its caption (above it on a horizontal pipe, beside it on a vertical one)
  const [ax, ay] = L.autofill;
  out.push(box(ax - 13, ay - 33, ax + 13, ay + 11, "autofill"));
  out.push(box(ax + 12, ay - 8, ax + 40, ay + 6, "autofill caption"));
  for (const l of L.labels) out.push(textBox(l.text, l.at, l.align ?? end, `label ${l.text}`));
  out.push(textBox("🌙 Ночь", L.badges.rad, end, "rad night badge", 11));
  out.push(textBox("🌙 Ночь", L.badges.floor, end, "floor night badge", 11));
  out.push(textBox("Анти-легионелла", L.badges.tank, end, "tank badge", 11));
  for (const k of ["rad", "floor", "coil"] as const) out.push(deltaBox(L.deltas[k], `${k} delta`));
  // manual-mode signs (same spots as in SchemeCanvas)
  out.push(around([L.ihbPump[0], L.ihbPump[1] - 20], 8, "ihb hint"));
  out.push(around([L.tank[0] + 70 * ts, L.tank[1] + 140 * ts], 8, "teh hint"));
  out.push(around([L.boiler[0] + (L.mirrored ? 10 : 110) * bs, L.boiler[1] + 10 * bs], 8, "boiler hint"));
  if (L.panel) out.push(box(L.panel.at[0], L.panel.at[1], L.panel.at[0] + L.panel.width, L.panel.at[1] + L.panel.height, "panel"));
  return out;
}

/** A circuit's "ΔT 88.8°" (11 px bold, centred, y = baseline) */
export function deltaBox([x, y]: Pt, what: string): Box {
  return box(x - 30, y - 11, x + 30, y + 3, what);
}

export function overlaps(a: Box, b: Box, gap = 0): boolean {
  return a.x0 < b.x1 + gap && b.x0 < a.x1 + gap && a.y0 < b.y1 + gap && b.y0 < a.y1 + gap;
}

/** Does the straight leg a→b pass through box `o`? (legs are horizontal or vertical) */
export function legHits([a, b]: [Pt, Pt], o: Box): boolean {
  // Liang–Barsky: clip the segment to the box (strictly inside, like `overlaps`); works for callouts too
  const [dx, dy] = [b[0] - a[0], b[1] - a[1]];
  let t0 = 0, t1 = 1;
  for (const [p, q] of [[-dx, a[0] - o.x0], [dx, o.x1 - a[0]], [-dy, a[1] - o.y0], [dy, o.y1 - a[1]]] as const) {
    if (p === 0) {
      if (q <= 0) return false;
      continue;
    }
    const r = q / p;
    if (p < 0) t0 = Math.max(t0, r);
    else t1 = Math.min(t1, r);
    if (t0 >= t1) return false;
  }
  return true;
}

/** Is the point on one of the pipe's segments (within its width)? */
export function onPipe(L: LayoutDef, [x, y]: Pt, match: (p: LayoutDef["pipes"][number]) => boolean): boolean {
  return L.pipes.filter(match).some((p) => p.points.slice(1).some((q, j) => {
    const a = p.points[j]!;
    return x >= Math.min(a[0], q[0]) - 0.5 && x <= Math.max(a[0], q[0]) + 0.5
      && y >= Math.min(a[1], q[1]) - 0.5 && y <= Math.max(a[1], q[1]) + 0.5;
  }));
}
