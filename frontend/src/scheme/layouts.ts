import type { PipeKind } from "./pipeColor";
import type { RelayName, RoleKey } from "./types";

export type LayoutName = "wide" | "tall";
type Pt = [number, number];

export interface PipeDef {
  kind: PipeKind;
  role?: RoleKey;            // temperature that colours the pipe
  flow?: RelayName | "any";  // relay that makes it flow ("any" = any circulation pump)
  points: Pt[];
}

export interface LayoutDef {
  width: number;
  height: number;
  boiler: Pt; separator: Pt; gauge: Pt; autofill: Pt; radiators: Pt; floor: Pt; tank: Pt; tap: Pt;
  radPump: Pt; radValve: Pt; floorPump: Pt; floorValve: Pt; ihbPump: Pt; recircPump: Pt; coldPump: Pt;
  tags: Partial<Record<RoleKey, Pt>>;
  labels: { text: string; at: Pt }[];
  badges: { rad: Pt; floor: Pt; tank: Pt };
  pipes: PipeDef[];
}

export const LAYOUTS: Record<LayoutName, LayoutDef> = {
  wide: {
    width: 1000, height: 560,
    boiler: [40, 250], separator: [330, 270], gauge: [466, 340], autofill: [300, 470],
    radiators: [250, 50], floor: [360, 470], tank: [700, 250], tap: [888, 222],
    radPump: [440, 175], radValve: [440, 223], floorPump: [440, 432], floorValve: [440, 455],
    ihbPump: [630, 300], recircPump: [840, 280], coldPump: [880, 420],
    tags: {
      boiler_supply: [175, 270], boiler_return: [175, 390], rad_supply: [455, 130], rad_return: [330, 140],
      floor_supply: [455, 400], floor_return: [330, 420], tank: [708, 320], coil_return: [590, 395],
      cold_water: [830, 440], hot_water: [912, 250], heating_pressure: [488, 332], water_pressure: [830, 462],
    },
    labels: [
      { text: "К1 Радиаторы", at: [350, 114] }, { text: "К2 Тёплый пол", at: [530, 505] },
      { text: "К3 Бойлер ГВС", at: [700, 460] }, { text: "Подпитка", at: [246, 498] },
    ],
    badges: { rad: [250, 130], floor: [530, 522], tank: [700, 478] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[160, 300], [330, 300]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[330, 380], [160, 380]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[440, 285], [440, 110], [285, 110], [285, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[380, 110], [380, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[475, 110], [475, 96]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[520, 96], [520, 122], [400, 122], [400, 365]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[300, 96], [300, 122], [400, 122]] },
      { kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[440, 315], [440, 470]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[400, 470], [400, 395]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[566, 300], [700, 300]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[700, 380], [566, 380]] },
      { kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[780, 280], [900, 280], [900, 248]] },
      { kind: "cold", role: "cold_water", flow: "water_pump", points: [[990, 420], [780, 420]] },
      { kind: "fill", flow: "af_open", points: [[990, 420], [990, 540], [230, 540], [230, 470], [348, 470], [348, 420]] },
    ],
  },
  tall: {
    width: 360, height: 640,
    boiler: [10, 250], separator: [130, 250], gauge: [180, 310], autofill: [150, 395],
    radiators: [55, 62], floor: [100, 470], tank: [285, 245], tap: [320, 205],
    radPump: [200, 170], radValve: [200, 215], floorPump: [200, 420], floorValve: [200, 445],
    ihbPump: [262, 280], recircPump: [330, 235], coldPump: [330, 395],
    tags: {
      boiler_supply: [12, 225], rad_supply: [215, 160], rad_return: [100, 160], floor_supply: [215, 470],
      tank: [282, 380], heating_pressure: [150, 355], cold_water: [20, 590], hot_water: [120, 590],
      water_pressure: [220, 590],
    },
    labels: [
      { text: "К1 Радиаторы", at: [130, 122] }, { text: "К2 Тёплый пол", at: [130, 540] },
      { text: "Бойлер", at: [288, 238] },
    ],
    badges: { rad: [130, 138], floor: [130, 556], tank: [282, 410] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[80, 280], [130, 280]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[130, 340], [80, 340]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[200, 265], [200, 105]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[165, 105], [165, 345]] },
      { kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[200, 345], [200, 470]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[165, 470], [165, 375]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[230, 280], [285, 280]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[285, 340], [230, 340]] },
      { kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[340, 260], [340, 225]] },
      { kind: "cold", role: "cold_water", flow: "water_pump", points: [[350, 420], [330, 420], [330, 430]] },
      { kind: "fill", flow: "af_open", points: [[148, 400], [148, 380]] },
    ],
  },
};

export function chooseLayout(width: number): LayoutName {
  return width >= 900 ? "wide" : "tall";
}
