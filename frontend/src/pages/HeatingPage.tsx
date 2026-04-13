import { useTranslation } from "react-i18next";
import TimeInput from "@/components/TimeInput";
import TipLabel from "@/components/TipLabel";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  Flame,
  Heater,
  Waves,
  Gauge,
  Calendar,
  Droplets,
  ThermometerSun,
} from "lucide-react";
import api from "@/api/client";
import { useDashboard } from "@/hooks/useDashboard";
import { useSettingUpdate } from "@/hooks/useSettingUpdate";
import {
  RADIATOR_CURVES,
  FLOOR_CURVES,
  interpolatePZA,
  type PZACurve,
} from "@/lib/pzaCurves";
import { fmt } from "@/lib/utils";
import CollapsibleSection from "@/components/CollapsibleSection";

function supplyGlow(actual: number | null | undefined, setpoint: number | null | undefined): string {
  if (actual == null || setpoint == null) return "font-semibold text-gray-800";
  if (actual > setpoint) return "font-bold temp-glow-red";
  if (actual < setpoint) return "font-bold temp-glow-blue";
  return "font-semibold text-gray-800";
}

function returnGlow(ret: number | null | undefined, supply: number | null | undefined): string {
  if (ret == null) return "font-semibold text-gray-800";
  if (supply != null && ret >= supply) return "font-bold temp-glow-red";
  return "font-bold text-blue-500";
}

/* ------------------------------------------------------------------ */
/*  Reusable UI primitives                                            */
/* ------------------------------------------------------------------ */

function Toggle({
  value,
  onChange,
  disabled,
  labelOn,
  labelOff,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  labelOn?: string;
  labelOff?: string;
}) {
  const { t } = useTranslation();
  const on = labelOn ?? t("dashboard.on");
  const off = labelOff ?? t("dashboard.off");
  return (
    <button
      disabled={disabled}
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-8 w-20 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
        disabled
          ? "cursor-not-allowed opacity-50"
          : "cursor-pointer"
      } ${value ? "bg-green-500" : "bg-gray-300 dark:bg-gray-600"}`}
    >
      <span
        className={`absolute text-[10px] font-semibold text-white transition-opacity ${
          value ? "left-2 opacity-100" : "left-2 opacity-0"
        }`}
      >
        {on}
      </span>
      <span
        className={`absolute text-[10px] font-semibold text-gray-500 dark:text-gray-200 transition-opacity ${
          value ? "right-2 opacity-0" : "right-2 opacity-100"
        }`}
      >
        {off}
      </span>
      <span
        className={`inline-block h-6 w-6 rounded-full bg-white shadow-md transition-transform ${
          value ? "translate-x-12" : "translate-x-1"
        }`}
      />
    </button>
  );
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <TipLabel text={label} tip={hint} className="text-sm text-gray-600" />
      <div className="flex items-center gap-2 shrink-0">{children}</div>
    </div>
  );
}

function TempSlider({
  value,
  min,
  max,
  unit,
  step,
  onChange,
  disabled,
  formatValue,
}: {
  value: number;
  min: number;
  max: number;
  unit?: string;
  step?: number;
  onChange: (v: number) => void;
  disabled?: boolean;
  formatValue?: (v: number) => string;
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        step={step ?? 1}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-32 sm:w-48 accent-primary-600 disabled:opacity-50"
      />
      <span className="min-w-[3.5rem] text-right text-sm font-medium text-gray-800">
        {formatValue ? formatValue(value) : value}
        {unit ?? "°C"}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  PZA chart with curve selector                                     */
/* ------------------------------------------------------------------ */

function PZAChart({
  curves,
  selectedCurve,
  onSelectCurve,
  outdoorTemp,
  maxY,
}: {
  curves: PZACurve[];
  selectedCurve: number;
  onSelectCurve: (i: number) => void;
  outdoorTemp?: number;
  maxY: number;
}) {
  const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed"];

  const chartData = curves[0]!.points.map((p) => {
    const row: Record<string, number> = { outdoor: p.outdoor };
    curves.forEach((curve, i) => {
      row[`c${i + 1}`] = interpolatePZA(curve, p.outdoor);
    });
    return row;
  });

  const currentSupply =
    outdoorTemp != null
      ? interpolatePZA(curves[selectedCurve]!, outdoorTemp)
      : null;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {curves.map((curve, i) => (
          <button
            key={i}
            onClick={() => onSelectCurve(i)}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              selectedCurve === i
                ? "bg-primary-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {curve.name}
          </button>
        ))}
        {currentSupply != null && outdoorTemp != null && (
          <span className="ml-auto text-xs text-gray-500">
            При {fmt(outdoorTemp)}°C = <strong>{fmt(currentSupply)}°C</strong>
          </span>
        )}
      </div>
      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="outdoor"
            reversed
            tick={{ fontSize: 11 }}
            label={{ value: "°C улица", position: "insideBottomRight", offset: -5, fontSize: 11 }}
          />
          <YAxis
            domain={[15, maxY]}
            tick={{ fontSize: 11 }}
            label={{ value: "°C подача", angle: -90, position: "insideLeft", fontSize: 11 }}
          />
          <Tooltip
            formatter={(v: number, name: string) => [`${v}°C`, name]}
            labelFormatter={(v) => `Улица: ${v}°C`}
          />
          {curves.map((_, i) => (
            <Line
              key={i}
              type="monotone"
              dataKey={`c${i + 1}`}
              name={curves[i]!.name}
              stroke={COLORS[i]}
              strokeWidth={selectedCurve === i ? 3 : 1}
              opacity={selectedCurve === i ? 1 : 0.25}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  PZA Indicators                                                    */
/* ------------------------------------------------------------------ */

function PZAIndicators({
  settings,
  outdoorTemp,
}: {
  settings: Record<string, string>;
  outdoorTemp?: number;
}) {
  const { t } = useTranslation();

  if (outdoorTemp == null) return null;

  const radWBM = settings.heating_radiator_wbm === "1";
  const floorWBM = settings.heating_floorheating_wbm === "1";
  const radCurve = Number(settings.heating_radiator_curve ?? "3") - 1;
  const floorCurve = Number(settings.heating_floorheating_curve ?? "3") - 1;

  const radPZA = interpolatePZA(
    RADIATOR_CURVES[Math.min(Math.max(radCurve, 0), 4)]!,
    outdoorTemp,
  );
  const floorPZA = interpolatePZA(
    FLOOR_CURVES[Math.min(Math.max(floorCurve, 0), 4)]!,
    outdoorTemp,
  );

  const radManual = Number(settings.heating_radiator_temp ?? "45");
  const floorManual = Number(settings.heating_floorheating_temp ?? "30");

  return (
    <section className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
        {t("heating.pzaIndicators")}
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <Indicator
          label={t("heating.outdoorTemp")}
          value={`${fmt(outdoorTemp)}°C`}
          icon={<ThermometerSun className="h-4 w-4 text-sky-500" />}
        />
        <Indicator
          label={t("heating.radiators")}
          value={radWBM ? `${fmt(radPZA)}°C` : `${fmt(radManual)}°C`}
          badge={radWBM ? `ПЗА кр.${radCurve + 1}` : "Ручн."}
          badgeColor={radWBM ? "green" : "gray"}
          hint={radWBM ? undefined : `по ПЗА ${fmt(radPZA)}°C`}
          icon={<Heater className="h-4 w-4 text-orange-500" />}
        />
        <Indicator
          label={t("heating.floorHeating")}
          value={floorWBM ? `${fmt(floorPZA)}°C` : `${fmt(floorManual)}°C`}
          badge={floorWBM ? `ПЗА кр.${floorCurve + 1}` : "Ручн."}
          badgeColor={floorWBM ? "green" : "gray"}
          hint={floorWBM ? undefined : `по ПЗА ${fmt(floorPZA)}°C`}
          icon={<Waves className="h-4 w-4 text-amber-500" />}
        />
        <Indicator
          label={t("heating.ihb")}
          value={`${settings.watersupply_ihb_temp ?? "45"}°C`}
          icon={<Droplets className="h-4 w-4 text-blue-500" />}
        />
      </div>
    </section>
  );
}

function Indicator({
  label,
  value,
  icon,
  badge,
  badgeColor,
  hint,
}: {
  label: string;
  value: string;
  icon: React.ReactNode;
  badge?: string;
  badgeColor?: "green" | "gray";
  hint?: string;
}) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
      {icon}
      <div>
        <div className="text-xs text-gray-500 flex items-center gap-1">
          {label}
          {badge && (
            <span className={`text-[9px] px-1 py-0.5 rounded ${
              badgeColor === "green"
                ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300"
                : "bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-200"
            }`}>
              {badge}
            </span>
          )}
        </div>
        <div className="text-sm font-semibold text-gray-800">
          {value}
          {hint && <span className="ml-1 text-[10px] font-normal text-gray-400">({hint})</span>}
        </div>
      </div>
    </div>
  );
}

/* ================================================================== */
/*  Main page                                                         */
/* ================================================================== */

export default function HeatingPage() {
  const { t } = useTranslation();
  const { data: dashboard } = useDashboard();
  const { update } = useSettingUpdate();

  const { data: settings } = useQuery<Record<string, string>>({
    queryKey: ["settings"],
    queryFn: async () => {
      const { data } = await api.get("/settings");
      return Object.fromEntries(
        (data as { key: string; value: string }[]).map((s) => [s.key, s.value]),
      );
    },
  });

  if (!settings) return null;

  const s = (key: string, fallback = "0") => settings[key] ?? fallback;
  const bool = (key: string) => s(key) === "1";
  const num = (key: string, fallback = "0") => Number(s(key, fallback));

  const outdoorTemp = dashboard?.climate?.find(
    (r) => r.room === "Улица",
  )?.temperature ?? undefined;

  /* ---- helpers ---- */
  const toggle = (key: string) =>
    update({ [key]: bool(key) ? "0" : "1" }, true);

  const set = (key: string, value: string | number) =>
    update({ [key]: String(value) });

  // Schedule helpers — write to both radiator and floor keys
  const schedBool = (suffix: string) => s(`heating_radiator_${suffix}`, "0") === "1";
  const schedVal = (suffix: string, fallback = "") => s(`heating_radiator_${suffix}`, fallback);
  const schedSet = (suffix: string, value: string) =>
    update({
      [`heating_radiator_${suffix}`]: value,
      [`heating_floorheating_${suffix}`]: value,
    });
  const schedToggle = (suffix: string) => {
    const v = schedBool(suffix) ? "0" : "1";
    schedSet(suffix, v);
  };

  const radCurveIdx = num("heating_radiator_curve", "3") - 1;
  const floorCurveIdx = num("heating_floorheating_curve", "3") - 1;

  const boilerAuto = bool("heating_boiler_automode");

  // Map circuit names to config keys for optimistic pump/temp display
  const circuitKeys: Record<string, { pump: string; temp: string }> = {
    "Котёл": { pump: "heating_boiler_power", temp: "heating_boiler_temp" },
    "Радиаторы": { pump: "heating_radiator_pump", temp: "heating_radiator_temp" },
    "Тёплый пол": { pump: "heating_floorheating_pump", temp: "heating_floorheating_temp" },
    "БКН": { pump: "watersupply_ihb_pump", temp: "watersupply_ihb_temp" },
  };

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold text-gray-800">{t("heating.title")}</h2>

      {/* PZA Indicators */}
      <PZAIndicators settings={settings} outdoorTemp={outdoorTemp} />

      {/* Heating Circuits Status */}
      {dashboard?.heating && dashboard.heating.length > 0 && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            {t("heating.circuitsStatus")}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {dashboard.heating.map((c) => {
              const keys = circuitKeys[c.circuit];
              const pumpOn = keys ? bool(keys.pump) : !!c.pump;
              // If PZA mode is on, use backend-calculated temp_set (from curve)
              // Otherwise use config_kv value (manual setpoint)
              const tempSet = c.pza_mode ? c.temp_set : (keys ? num(keys.temp, String(c.temp_set ?? 0)) : c.temp_set);
              return (
                <div
                  key={c.circuit}
                  className="rounded-lg border border-gray-100 bg-gray-50 p-3"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800 text-sm">{c.circuit}</span>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        pumpOn
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-200 text-gray-500"
                      }`}
                    >
                      {pumpOn ? t("dashboard.on") : t("dashboard.off")}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs text-gray-600">
                    <div className="flex justify-between items-center">
                      <span className="flex items-center gap-1">
                        {t("dashboard.tempSet")}
                        {c.pza_mode ? (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
                            ПЗА кр.{c.pza_curve}
                          </span>
                        ) : c.pza_capable ? (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-gray-200 text-gray-700 dark:bg-gray-600 dark:text-gray-200">
                            Ручн.
                          </span>
                        ) : null}
                      </span>
                      <span className="font-semibold text-gray-800">
                        {fmt(tempSet)}°C
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("dashboard.tempSupply")}</span>
                      <span className={supplyGlow(c.temp_supply, tempSet)}>
                        {fmt(c.temp_supply)}°C
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("dashboard.tempReturn")}</span>
                      <span className={returnGlow(c.temp_return, c.temp_supply)}>
                        {fmt(c.temp_return)}°C
                      </span>
                    </div>
                    {c.pressure != null && (
                      <div className="flex justify-between">
                        <span>{t("dashboard.pressure")}</span>
                        <span className="font-semibold text-gray-800">
                          {fmt(c.pressure)} {t("heating.bar")}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Boiler + IHB side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Boiler */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("heating.boiler")} icon={Flame}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("heating.autoRegulation")} hint={t("heating.hints.autoRegulation")}>
                <Toggle value={boilerAuto} onChange={() => toggle("heating_boiler_automode")} />
              </SettingRow>
              <SettingRow label={t("heating.boilerPower")} hint={t("heating.hints.boilerPower")}>
                <Toggle
                  value={bool("heating_boiler_power")}
                  onChange={() => toggle("heating_boiler_power")}
                  disabled={boilerAuto}
                />
              </SettingRow>
              <SettingRow label={t("heating.boilerTemp")} hint={t("heating.hints.boilerTemp")}>
                <TempSlider
                  value={num("heating_boiler_temp", "50")}
                  min={30}
                  max={90}
                  onChange={(v) => set("heating_boiler_temp", v)}
                  disabled={boilerAuto}
                />
              </SettingRow>
              <SettingRow label={t("heating.boilerMaxTemp")} hint={t("heating.hints.boilerMaxTemp")}>
                <TempSlider
                  value={num("heating_boiler_max_temp", "85")}
                  min={60}
                  max={95}
                  onChange={(v) => set("heating_boiler_max_temp", v)}
                />
              </SettingRow>
            </div>
            {boilerAuto && (
              <p className="mt-2 text-xs text-amber-600">
                {t("heating.autoRegulationHint")}
              </p>
            )}
          </CollapsibleSection>
        </section>

        {/* IHB (БКН) */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("heating.ihb")} icon={Droplets}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("waterSupply.ihbAutoMode")} hint={t("waterSupply.hints.ihbAutoMode")}>
                <Toggle
                  value={bool("watersupply_ihb_automode")}
                  onChange={() => toggle("watersupply_ihb_automode")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.ihbPump")} hint={t("waterSupply.hints.ihbPump")}>
                <Toggle
                  value={bool("watersupply_ihb_pump")}
                  onChange={() => toggle("watersupply_ihb_pump")}
                  disabled={bool("watersupply_ihb_automode")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.ihbTemp")} hint={t("waterSupply.hints.ihbTemp")}>
                <TempSlider
                  value={num("watersupply_ihb_temp", "45")}
                  min={40}
                  max={70}
                  onChange={(v) => set("watersupply_ihb_temp", v)}
                />
              </SettingRow>
            </div>
            {bool("watersupply_ihb_automode") && (
              <p className="mt-2 text-xs text-amber-600">
                {t("waterSupply.ihbAutoHint")}
              </p>
            )}
          </CollapsibleSection>
        </section>
      </div>

      {/* Radiators + Floor Heating side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Radiators */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("heating.radiators")} icon={Heater}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("heating.pzaMode")} hint={t("heating.hints.pzaMode")}>
                <Toggle
                  value={bool("heating_radiator_wbm")}
                  onChange={() => toggle("heating_radiator_wbm")}
                />
              </SettingRow>
              <SettingRow label={t("dashboard.pump")} hint={t("heating.hints.pump")}>
                <Toggle
                  value={bool("heating_radiator_pump")}
                  onChange={() => toggle("heating_radiator_pump")}
                  disabled={bool("heating_radiator_wbm")}
                />
              </SettingRow>
              <SettingRow label={t("heating.supplyTemp")} hint={t("heating.hints.supplyTemp")}>
                <TempSlider
                  value={num("heating_radiator_temp", "45")}
                  min={30}
                  max={90}
                  onChange={(v) => set("heating_radiator_temp", v)}
                  disabled={bool("heating_radiator_wbm")}
                />
              </SettingRow>
              <SettingRow label={t("heating.disableDuringIHB")} hint={t("heating.hints.disableDuringIHB")}>
                <Toggle
                  value={bool("heating_radiator_off_ihb")}
                  onChange={() => toggle("heating_radiator_off_ihb")}
                />
              </SettingRow>
            </div>

            {/* Radiator PZA Chart */}
            {bool("heating_radiator_wbm") && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="text-sm font-medium text-gray-600 mb-2">
                  {t("heating.pzaCurve")}
                </h4>
                <PZAChart
                  curves={RADIATOR_CURVES}
                  selectedCurve={Math.min(Math.max(radCurveIdx, 0), 4)}
                  onSelectCurve={(i) => set("heating_radiator_curve", i + 1)}
                  outdoorTemp={outdoorTemp}
                  maxY={90}
                />
              </div>
            )}
          </CollapsibleSection>
        </section>

        {/* Floor Heating */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("heating.floorHeating")} icon={Waves}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("heating.pzaMode")} hint={t("heating.hints.pzaMode")}>
                <Toggle
                  value={bool("heating_floorheating_wbm")}
                  onChange={() => toggle("heating_floorheating_wbm")}
                />
              </SettingRow>
              <SettingRow label={t("dashboard.pump")} hint={t("heating.hints.pump")}>
                <Toggle
                  value={bool("heating_floorheating_pump")}
                  onChange={() => toggle("heating_floorheating_pump")}
                  disabled={bool("heating_floorheating_wbm")}
                />
              </SettingRow>
              <SettingRow label={t("heating.supplyTemp")} hint={t("heating.hints.supplyTemp")}>
                <TempSlider
                  value={num("heating_floorheating_temp", "30")}
                  min={25}
                  max={35}
                  onChange={(v) => set("heating_floorheating_temp", v)}
                  disabled={bool("heating_floorheating_wbm")}
                />
              </SettingRow>
              <SettingRow label={t("heating.disableDuringIHB")} hint={t("heating.hints.disableDuringIHB")}>
                <Toggle
                  value={bool("heating_floorheating_off_ihb")}
                  onChange={() => toggle("heating_floorheating_off_ihb")}
                />
              </SettingRow>
            </div>

            {/* Floor PZA Chart */}
            {bool("heating_floorheating_wbm") && (
              <div className="mt-4 pt-4 border-t border-gray-100">
                <h4 className="text-sm font-medium text-gray-600 mb-2">
                  {t("heating.pzaCurve")}
                </h4>
                <PZAChart
                  curves={FLOOR_CURVES}
                  selectedCurve={Math.min(Math.max(floorCurveIdx, 0), 4)}
                  onSelectCurve={(i) => set("heating_floorheating_curve", i + 1)}
                  outdoorTemp={outdoorTemp}
                  maxY={45}
                />
              </div>
            )}
          </CollapsibleSection>
        </section>
      </div>

      {/* Schedule + Auto-fill side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Schedule */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("heating.schedule")} icon={Calendar}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("heating.scheduleEnabled")} hint={t("heating.hints.scheduleEnabled")}>
                <Toggle
                  value={schedBool("schedule_enabled")}
                  onChange={() => schedToggle("schedule_enabled")}
                />
              </SettingRow>
              <SettingRow label={t("heating.scheduleDeltaRadiators")} hint={t("heating.hints.scheduleDelta")}>
                <TempSlider
                  value={num("heating_radiator_schedule_delta", "-10")}
                  min={-20}
                  max={0}
                  onChange={(v) => set("heating_radiator_schedule_delta", v)}
                  disabled={!schedBool("schedule_enabled")}
                />
              </SettingRow>
              <SettingRow label={t("heating.scheduleDeltaFloor")} hint={t("heating.hints.scheduleDelta")}>
                <TempSlider
                  value={num("heating_floorheating_schedule_delta", "-5")}
                  min={-20}
                  max={0}
                  onChange={(v) => set("heating_floorheating_schedule_delta", v)}
                  disabled={!schedBool("schedule_enabled")}
                />
              </SettingRow>
            </div>
            {schedBool("schedule_enabled") && (
              <>
                <div className="mt-3 flex items-center justify-between gap-3 flex-wrap">
                  <div>
                    <p className="text-xs font-medium text-gray-600 mb-1.5">{t("heating.scheduleDays")}</p>
                    <div className="flex gap-1.5">
                      {[1, 2, 3, 4, 5, 6, 7].map((d) => {
                        const days = (schedVal("schedule_days", "1,2,3,4,5")).split(",").filter(Boolean);
                        const active = days.includes(String(d));
                        const labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
                        return (
                          <button
                            key={d}
                            onClick={() => {
                              const ds = new Set(days.map(Number));
                              if (ds.has(d)) ds.delete(d); else ds.add(d);
                              schedSet("schedule_days", Array.from(ds).sort().join(","));
                            }}
                            className={`px-2.5 py-1 rounded-lg text-xs font-semibold border transition-colors ${
                              active
                                ? "bg-primary-600 text-white border-primary-600"
                                : "bg-gray-50 text-gray-500 border-gray-200 hover:border-gray-300"
                            }`}
                          >
                            {labels[d - 1]}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <div>
                    <p className="text-xs font-medium text-gray-600 mb-1.5">{t("heating.scheduleHours")}</p>
                    <div className="flex items-center gap-1.5">
                      <TimeInput
                        value={schedVal("schedule_start", "23:00")}
                        onChange={(v) => schedSet("schedule_start", v)}
                      />
                      <span className="text-gray-400 text-sm">—</span>
                      <TimeInput
                        value={schedVal("schedule_end", "06:00")}
                        onChange={(v) => schedSet("schedule_end", v)}
                      />
                    </div>
                  </div>
                </div>
                <p className="mt-2 text-xs text-gray-500">
                  {t("heating.scheduleDeltaHint")}
                </p>
              </>
            )}
          </CollapsibleSection>
        </section>

        {/* Auto-fill / Pressure */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("heating.autofill")} icon={Gauge}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("heating.autofillEnabled")} hint={t("heating.hints.autofillEnabled")}>
                <Toggle
                  value={bool("heating_autofill_enabled")}
                  onChange={() => toggle("heating_autofill_enabled")}
                />
              </SettingRow>
              <SettingRow label={t("heating.pressureMin")} hint={t("heating.hints.pressureMin")}>
                <TempSlider
                  value={num("heating_pressure_min", "1.0") * 10}
                  min={1}
                  max={30}
                  unit=" бар"
                  onChange={(v) => {
                    if (v / 10 >= num("heating_pressure_max", "1.8")) return;
                    set("heating_pressure_min", (v / 10).toFixed(1));
                  }}
                  disabled={!bool("heating_autofill_enabled")}
                  formatValue={(v) => (v / 10).toFixed(1)}
                />
              </SettingRow>
              <SettingRow label={t("heating.pressureMax")} hint={t("heating.hints.pressureMax")}>
                <TempSlider
                  value={num("heating_pressure_max", "1.8") * 10}
                  min={1}
                  max={30}
                  unit=" бар"
                  onChange={(v) => {
                    if (v / 10 <= num("heating_pressure_min", "1.0")) return;
                    set("heating_pressure_max", (v / 10).toFixed(1));
                  }}
                  disabled={!bool("heating_autofill_enabled")}
                  formatValue={(v) => (v / 10).toFixed(1)}
                />
              </SettingRow>
            </div>
          </CollapsibleSection>
        </section>
      </div>
    </div>
  );
}
