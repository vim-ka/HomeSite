import type { ElementKind } from "./types";

export interface FieldDef {
  key: string;
  label: string;
  type: "bool" | "number" | "curve";
  min?: number; max?: number; step?: number; unit?: string;
  disabledWhen?: (v: Record<string, string>) => boolean;
}

export interface FormDef { title: string; fields: FieldDef[]; link?: { to: string; text: string } }

const circuit = (p: "heating_radiator" | "heating_floorheating", title: string, max: number): FormDef => ({
  title,
  fields: [
    { key: `${p}_pump`, label: "Насос", type: "bool" },
    { key: `${p}_wbm`, label: "ПЗА (погодозависимая)", type: "bool" },
    { key: `${p}_curve`, label: "Кривая ПЗА", type: "curve", disabledWhen: (v) => v[`${p}_wbm`] !== "1" },
    { key: `${p}_temp`, label: "Ручная уставка подачи", type: "number", min: 20, max, step: 1, unit: "°C",
      disabledWhen: (v) => v[`${p}_wbm`] === "1" },
    { key: `${p}_off_ihb`, label: "Отключать при нагреве БКН", type: "bool" },
  ],
  link: { to: "/heating", text: "Расписание и графики кривых → Отопление" },
});

export const FORMS: Record<Exclude<ElementKind, "sensor">, FormDef> = {
  boiler: {
    title: "Котёл",
    fields: [
      { key: "heating_boiler_automode", label: "Автоматический режим", type: "bool" },
      { key: "heating_boiler_power", label: "Питание котла", type: "bool", disabledWhen: (v) => v.heating_boiler_automode === "1" },
      { key: "heating_boiler_temp", label: "Уставка котла", type: "number", min: 30, max: 90, step: 1, unit: "°C" },
      { key: "heating_boiler_max_temp", label: "Макс. температура котла", type: "number", min: 60, max: 90, step: 1, unit: "°C" },
    ],
  },
  autofill: {
    title: "Давление и автоподпитка",
    fields: [
      { key: "heating_autofill_enabled", label: "Автоподпитка", type: "bool" },
      { key: "heating_pressure_min", label: "Давление min", type: "number", min: 0.5, max: 2.0, step: 0.1, unit: "бар" },
      { key: "heating_pressure_max", label: "Давление max", type: "number", min: 1.0, max: 2.8, step: 0.1, unit: "бар" },
    ],
  },
  rad: circuit("heating_radiator", "Радиаторы", 90),
  floor: circuit("heating_floorheating", "Тёплый пол", 50),
  tank: {
    title: "Бойлер ГВС",
    fields: [
      { key: "watersupply_ihb_automode", label: "Авто-режим БКН", type: "bool" },
      { key: "watersupply_ihb_pump", label: "Насос загрузки", type: "bool", disabledWhen: (v) => v.watersupply_ihb_automode === "1" },
      { key: "watersupply_ihb_temp", label: "Уставка бойлера", type: "number", min: 30, max: 75, step: 1, unit: "°C" },
      { key: "watersupply_ihb_teh_automode", label: "ТЭН авто", type: "bool" },
      { key: "watersupply_ihb_teh_power", label: "ТЭН вкл", type: "bool", disabledWhen: (v) => v.watersupply_ihb_teh_automode === "1" },
      { key: "watersupply_ihb_teh_heating_delay", label: "Задержка ТЭН", type: "number", min: 0, max: 240, step: 5, unit: "мин" },
    ],
    link: { to: "/water-supply", text: "Анти-легионелла → Водоснабжение" },
  },
  cold: { title: "Холодная вода", fields: [{ key: "watersupply_pump", label: "Насос ХВС", type: "bool" }] },
  hot: { title: "Горячая вода", fields: [{ key: "watersupply_pump_hot", label: "Рециркуляция ГВС", type: "bool" }] },
};
