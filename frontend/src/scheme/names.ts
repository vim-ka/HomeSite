import type { RoleKey } from "./types";

/** Human names of the scheme's sensor roles (dialogs, aria-labels). */
export const ROLE_LABELS: Partial<Record<RoleKey, string>> = {
  boiler_supply: "Подача котла", boiler_return: "Обратка котла", rad_supply: "Подача радиаторов",
  rad_return: "Обратка радиаторов", floor_supply: "Подача пола", floor_return: "Обратка пола",
  tank: "Бойлер", coil_supply: "Подача в змеевик", coil_return: "Обратка змеевика", cold_water: "Холодная вода",
  heating_pressure: "Давление контура", water_pressure: "Давление ХВС", outdoor: "Улица",
  indoor_avg: "Дом", boiler_room: "Котельная",
};

/** Human names of the scheme's clickable elements (aria-labels for screen readers). */
export const ELEMENT_NAMES: Record<string, string> = {
  radiators: "Радиаторы", rad_pump: "Насос радиаторов", rad_valve: "Смесительный клапан радиаторов",
  floor: "Тёплый пол", floor_pump: "Насос тёплого пола", floor_valve: "Смесительный клапан тёплого пола",
  boiler: "Котёл", separator: "Гидрострелка и коллектор", gauge: "Манометр", autofill: "Автоподпитка",
  tank: "Бойлер ГВС", ihb_pump: "Насос бойлера", recirc_pump: "Рециркуляция ГВС", cold_pump: "Насос ХВС",
  tap: "Горячая вода", cold_tap: "Холодная вода", well: "Скважина", teh: "ТЭН бойлера",
};

export function elementName(id: string): string {
  if (id.startsWith("tag_")) return ROLE_LABELS[id.slice(4) as RoleKey] ?? id;
  return ELEMENT_NAMES[id] ?? id;
}
