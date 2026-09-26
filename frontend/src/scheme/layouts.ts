import type { PipeKind } from "./pipeColor";
import type { RelayName, RoleKey } from "./types";

export type LayoutName = "wide" | "tall";
type Pt = [number, number];

export interface PipeDef {
  id?: string;               // stable name for tests / debugging (data-pipe)
  kind: PipeKind;
  role?: RoleKey;            // temperature that colours the pipe
  flow?: RelayName | "any";  // relay that makes it flow ("any" = any circulation pump)
  points: Pt[];
}

export interface LayoutDef {
  width: number;
  height: number;
  boiler: Pt; separator: Pt; gauge: Pt; autofill: Pt; radiators: Pt; floor: Pt; tank: Pt; tap: Pt; well: Pt;
  radPump: Pt; radValve: Pt; floorPump: Pt; floorValve: Pt; ihbPump: Pt; recircPump: Pt; coldPump: Pt;
  boilerScale?: number; tankScale?: number; collectorWidth?: number;
  tags: Partial<Record<RoleKey, Pt>>;
  labels: { text: string; at: Pt }[];
  badges: { rad: Pt; floor: Pt; tank: Pt };
  pipes: PipeDef[];
}

export const LAYOUTS: Record<LayoutName, LayoutDef> = {
  wide: {
    width: 1000, height: 560,
    boiler: [40, 250], separator: [330, 270], gauge: [466, 340], autofill: [300, 470],
    radiators: [250, 50], floor: [360, 470], tank: [700, 250], tap: [888, 222], well: [30, 468],
    radPump: [440, 175], radValve: [440, 223], floorPump: [440, 432], floorValve: [440, 455],
    ihbPump: [630, 300], recircPump: [880, 375], coldPump: [130, 470],
    tags: {
      boiler_supply: [175, 270], boiler_return: [175, 390], rad_supply: [455, 130], rad_return: [330, 140],
      floor_supply: [455, 400], floor_return: [330, 420], tank: [708, 320], coil_return: [590, 395],
      hot_water: [912, 250], heating_pressure: [488, 332], cold_water: [92, 490], water_pressure: [92, 512],
    },
    labels: [
      { text: "Радиаторы", at: [250, 40] }, { text: "Тёплый пол", at: [530, 505] },
      { text: "Бойлер ГВС", at: [700, 460] }, { text: "Подпитка", at: [246, 498] },
      { text: "Скважина", at: [22, 462] }, { text: "Рециркуляция", at: [800, 400] },
    ],
    badges: { rad: [250, 22], floor: [530, 522], tank: [700, 478] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[160, 300], [330, 300]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[330, 380], [160, 380]] },
      // radiators at x 250/345/440 (70 wide): supply to the left bottom port (+8), return from the right (+62)
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[312, 96], [312, 124], [502, 124], [502, 96]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[407, 96], [407, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[400, 124], [400, 365]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[258, 96], [258, 110], [448, 110], [448, 96]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[353, 96], [353, 110]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[440, 285], [440, 110]] },
      { kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[440, 315], [440, 470]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[400, 470], [400, 395]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[566, 300], [700, 300]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[700, 380], [566, 380]] },
      // DHW: tank top → tap; recirculation loop returns from the tap into the tank (pump on the return)
      { id: "hot_to_tap", kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[780, 280], [900, 280], [900, 248]] },
      { id: "recirc_return", kind: "hot", flow: "water_hot_pump", points: [[900, 280], [960, 280], [960, 375], [780, 375]] },
      // cold water: well → pump → branch to autofill and to the tank bottom
      { id: "cold_from_well", kind: "cold", role: "cold_water", flow: "water_pump", points: [[55, 470], [200, 470]] },
      { id: "cold_to_fill", kind: "fill", flow: "af_open", points: [[200, 470], [348, 470], [348, 420]] },
      { id: "cold_to_tank", kind: "cold", role: "cold_water", flow: "water_pump", points: [[200, 470], [200, 545], [740, 545], [740, 436]] },
    ],
  },
  tall: {
    width: 360, height: 640,
    boiler: [8, 250], separator: [110, 240], gauge: [230, 310], autofill: [120, 505],
    radiators: [50, 62], floor: [100, 470], tank: [290, 250], tap: [302, 190], well: [8, 552],
    radPump: [200, 170], radValve: [200, 215], floorPump: [200, 420], floorValve: [200, 445],
    ihbPump: [273, 270], recircPump: [346, 290], coldPump: [80, 560],
    boilerScale: 0.55, tankScale: 0.6, collectorWidth: 110,
    tags: {
      boiler_supply: [8, 226], rad_supply: [208, 150], rad_return: [95, 150], floor_supply: [210, 380],
      tank: [262, 372], heating_pressure: [30, 398], hot_water: [236, 196],
      cold_water: [150, 575], water_pressure: [226, 575],
    },
    labels: [
      { text: "Радиаторы", at: [50, 54] }, { text: "Тёплый пол", at: [130, 540] },
      { text: "Бойлер", at: [290, 242] }, { text: "Скважина", at: [6, 545] },
    ],
    badges: { rad: [180, 54], floor: [230, 540], tank: [262, 410] },
    pipes: [
      { kind: "supply", role: "boiler_supply", flow: "any", points: [[74, 280], [110, 280]] },
      { kind: "return", role: "boiler_return", flow: "any", points: [[110, 350], [74, 350]] },
      // radiators at x 50/145/240: supply to the left bottom ports (+8), return from the right ones (+62)
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[112, 108], [112, 124], [302, 124], [302, 108]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[207, 108], [207, 124]] },
      { kind: "return", role: "rad_return", flow: "rad_pump", points: [[165, 124], [165, 335]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[58, 108], [58, 114], [248, 114], [248, 108]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[153, 108], [153, 114]] },
      { kind: "supply", role: "rad_supply", flow: "rad_pump", points: [[200, 255], [200, 114]] },
      { kind: "supply", role: "floor_supply", flow: "floor_pump", points: [[200, 285], [200, 470]] },
      { kind: "return", role: "floor_return", flow: "floor_pump", points: [[165, 470], [165, 365]] },
      { kind: "supply", role: "boiler_supply", flow: "ihb_pump", points: [[256, 270], [290, 270]] },
      { kind: "return", role: "coil_return", flow: "ihb_pump", points: [[290, 350], [256, 350]] },
      { id: "hot_to_tap", kind: "hot", role: "hot_water", flow: "water_hot_pump", points: [[314, 250], [314, 214]] },
      { id: "recirc_return", kind: "hot", flow: "water_hot_pump", points: [[314, 232], [346, 232], [346, 330], [338, 330]] },
      { id: "cold_from_well", kind: "cold", role: "cold_water", flow: "water_pump", points: [[33, 556], [120, 556]] },
      { id: "cold_to_fill", kind: "fill", flow: "af_open", points: [[120, 556], [120, 440], [128, 440], [128, 390]] },
      { id: "cold_to_tank", kind: "cold", role: "cold_water", flow: "water_pump", points: [[120, 556], [314, 556], [314, 364]] },
    ],
  },
};

export function chooseLayout(width: number): LayoutName {
  return width >= 900 ? "wide" : "tall";
}
