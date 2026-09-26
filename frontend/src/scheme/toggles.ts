import type { RelayName } from "./types";

/** On/off controls reachable by a left click on the scheme. */
export interface ToggleDef {
  key: string;
  label: string;
  /** relay that reflects the setting — used when the setting itself is unknown */
  relay?: RelayName;
}

/** Scheme element id → setting it switches. */
export const TOGGLES: Record<string, ToggleDef> = {
  rad_pump: { key: "heating_radiator_pump", label: "Насос радиаторов", relay: "rad_pump" },
  floor_pump: { key: "heating_floorheating_pump", label: "Насос тёплого пола", relay: "floor_pump" },
  ihb_pump: { key: "watersupply_ihb_pump", label: "Насос бойлера", relay: "ihb_pump" },
  recirc_pump: { key: "watersupply_pump_hot", label: "Рециркуляция ГВС", relay: "water_hot_pump" },
  cold_pump: { key: "watersupply_pump", label: "Насос ХВС", relay: "water_pump" },
  boiler: { key: "heating_boiler_power", label: "Котёл", relay: "boiler" },
  autofill: { key: "heating_autofill_enabled", label: "Автоподпитка" },
};

/** Why a quick toggle would have no effect right now (the controller ignores it), or null. */
export function toggleLock(key: string, settings: Record<string, string>): string | null {
  if (key === "heating_boiler_power" && settings.heating_boiler_automode === "1") {
    return "Котёл в авто-режиме — управление по правому клику";
  }
  if (key === "watersupply_ihb_pump" && settings.watersupply_ihb_automode === "1") {
    return "Насос бойлера в авто-режиме — управление по правому клику";
  }
  return null;
}

/** Commanded on/off state: the setting, or the relay when the setting is unknown. */
export function isOn(def: ToggleDef, settings: Record<string, string>, relays: Record<RelayName, boolean>): boolean {
  const value = settings[def.key];
  if (value !== undefined) return value === "1";
  return def.relay ? relays[def.relay] : false;
}
