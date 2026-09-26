/** On/off controls reachable by a left click on the scheme. */
export interface ToggleDef { key: string; label: string }

/** Scheme element id → setting it switches. */
export const TOGGLES: Record<string, ToggleDef> = {
  rad_pump: { key: "heating_radiator_pump", label: "Насос радиаторов" },
  floor_pump: { key: "heating_floorheating_pump", label: "Насос тёплого пола" },
  ihb_pump: { key: "watersupply_ihb_pump", label: "Насос бойлера" },
  recirc_pump: { key: "watersupply_pump_hot", label: "Рециркуляция ГВС" },
  cold_pump: { key: "watersupply_pump", label: "Насос ХВС" },
  boiler: { key: "heating_boiler_power", label: "Котёл" },
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
