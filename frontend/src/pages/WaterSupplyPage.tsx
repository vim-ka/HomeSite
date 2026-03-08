import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Flame,
  Zap,
  ShieldCheck,
  Waves,
} from "lucide-react";
import api from "@/api/client";
import { useDashboard } from "@/hooks/useDashboard";
import { useSettingUpdate } from "@/hooks/useSettingUpdate";
import { fmt } from "@/lib/utils";
import CollapsibleSection from "@/components/CollapsibleSection";

function supplyGlow(actual: number | null | undefined, setpoint: number | null | undefined): string {
  if (actual == null || setpoint == null) return "font-semibold text-gray-800";
  if (actual > setpoint) return "font-bold temp-glow-red";
  if (actual < setpoint) return "font-bold temp-glow-blue";
  return "font-semibold text-gray-800";
}

/* ------------------------------------------------------------------ */
/*  Reusable UI primitives (same style as HeatingPage)                */
/* ------------------------------------------------------------------ */

function Toggle({
  value,
  onChange,
  disabled,
}: {
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <button
      disabled={disabled}
      onClick={() => onChange(!value)}
      className={`relative inline-flex h-8 w-20 shrink-0 items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 ${
        disabled ? "cursor-not-allowed opacity-50" : "cursor-pointer"
      } ${value ? "bg-green-500" : "bg-gray-300"}`}
    >
      <span
        className={`absolute text-[10px] font-semibold text-white transition-opacity ${
          value ? "left-2 opacity-100" : "left-2 opacity-0"
        }`}
      >
        {t("dashboard.on")}
      </span>
      <span
        className={`absolute text-[10px] font-semibold text-gray-600 transition-opacity ${
          value ? "right-2 opacity-0" : "right-2 opacity-100"
        }`}
      >
        {t("dashboard.off")}
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
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <span className="text-sm text-gray-600">{label}</span>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  );
}

function TempSlider({
  value,
  min,
  max,
  unit,
  onChange,
  disabled,
}: {
  value: number;
  min: number;
  max: number;
  unit?: string;
  onChange: (v: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <input
        type="range"
        min={min}
        max={max}
        step={1}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-32 sm:w-48 accent-primary-600 disabled:opacity-50"
      />
      <span className="min-w-[3.5rem] text-right text-sm font-medium text-gray-800">
        {value}
        {unit ?? "°C"}
      </span>
    </div>
  );
}

function TimeWheel({ value, options, onChange }: { value: number; options: number[]; onChange: (v: number) => void }) {
  const idx = options.indexOf(value);
  const prev = () => onChange(options[(idx - 1 + options.length) % options.length]!);
  const next = () => onChange(options[(idx + 1) % options.length]!);
  return (
    <div className="flex flex-col items-center leading-none">
      <button onClick={prev} className="text-gray-400 hover:text-gray-600 text-[10px]">▲</button>
      <span className="text-base font-semibold text-gray-800 tabular-nums w-7 text-center">
        {String(value).padStart(2, "0")}
      </span>
      <button onClick={next} className="text-gray-400 hover:text-gray-600 text-[10px]">▼</button>
    </div>
  );
}

function TimeInput({ value, onChange, disabled }: { value: string; onChange: (v: string) => void; disabled?: boolean }) {
  const [h, m] = value.split(":").map(Number);
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const minutes = [0, 15, 30, 45];
  return (
    <div className={`inline-flex items-center gap-0 rounded-lg border border-gray-200 bg-white px-2 py-0.5 ${disabled ? "opacity-50 pointer-events-none" : ""}`}>
      <TimeWheel
        value={h ?? 0}
        options={hours}
        onChange={(v) => onChange(`${String(v).padStart(2, "0")}:${String(m ?? 0).padStart(2, "0")}`)}
      />
      <span className="text-gray-400 font-bold text-base mx-0.5">:</span>
      <TimeWheel
        value={m ?? 0}
        options={minutes}
        onChange={(v) => onChange(`${String(h ?? 0).padStart(2, "0")}:${String(v).padStart(2, "0")}`)}
      />
    </div>
  );
}

const DAYS = [
  { key: "1", label: "Пн" },
  { key: "2", label: "Вт" },
  { key: "3", label: "Ср" },
  { key: "4", label: "Чт" },
  { key: "5", label: "Пт" },
  { key: "6", label: "Сб" },
  { key: "7", label: "Вс" },
];

/* ================================================================== */
/*  Main page                                                         */
/* ================================================================== */

export default function WaterSupplyPage() {
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

  const toggle = (key: string) =>
    update({ [key]: bool(key) ? "0" : "1" }, true);

  const set = (key: string, value: string | number) =>
    update({ [key]: String(value) });

  const ihbAuto = bool("watersupply_ihb_automode");
  const almEnabled = bool("watersupply_ihb_alm_mode");

  // Anti-legionella days
  const almDays = s("watersupply_alm_days", "").split(",").filter(Boolean);
  const toggleDay = (day: string) => {
    const next = almDays.includes(day)
      ? almDays.filter((d) => d !== day)
      : [...almDays, day];
    set("watersupply_alm_days", next.join(","));
  };

  return (
    <div className="space-y-5">
      <h2 className="text-xl font-bold text-gray-800">{t("waterSupply.title")}</h2>

      {/* Water Supply Status */}
      {dashboard?.water_supply && dashboard.water_supply.length > 0 && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            {t("waterSupply.currentReadings")}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {dashboard.water_supply.map((w) => {
              const isHot = w.type.toLowerCase().includes("горяч");
              const pumpKey = isHot ? "watersupply_pump_hot" : "watersupply_pump";
              const pumpOn = bool(pumpKey);
              return (
                <div
                  key={w.type}
                  className="rounded-lg border border-gray-100 bg-gray-50 p-3"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-800 text-sm">{w.type}</span>
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
                    <div className="flex justify-between">
                      <span>{t("dashboard.tempSet")}</span>
                      <span className="font-semibold text-gray-800">
                        {fmt(w.temp_set)}°C
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>{t("waterSupply.actual")}</span>
                      <span className={supplyGlow(w.temp_fact, w.temp_set)}>
                        {fmt(w.temp_fact)}°C
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* IHB + Pumps side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* IHB (БКН) */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("waterSupply.ihb")} icon={Flame}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("waterSupply.ihbAutoMode")}>
                <Toggle
                  value={ihbAuto}
                  onChange={() => toggle("watersupply_ihb_automode")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.ihbPump")}>
                <Toggle
                  value={bool("watersupply_ihb_pump")}
                  onChange={() => toggle("watersupply_ihb_pump")}
                  disabled={ihbAuto}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.ihbTemp")}>
                <TempSlider
                  value={num("watersupply_ihb_temp", "45")}
                  min={40}
                  max={70}
                  onChange={(v) => set("watersupply_ihb_temp", v)}
                  disabled={ihbAuto}
                />
              </SettingRow>
            </div>
            {ihbAuto && (
              <p className="mt-2 text-xs text-amber-600">
                {t("waterSupply.ihbAutoHint")}
              </p>
            )}
          </CollapsibleSection>
        </section>

        {/* Pumps */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("waterSupply.pumps")} icon={Waves}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("waterSupply.coldPump")}>
                <Toggle
                  value={bool("watersupply_pump")}
                  onChange={() => toggle("watersupply_pump")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.hotPump")}>
                <Toggle
                  value={bool("watersupply_pump_hot")}
                  onChange={() => toggle("watersupply_pump_hot")}
                />
              </SettingRow>
            </div>
          </CollapsibleSection>
        </section>
      </div>

      {/* TEN + Anti-legionella side by side */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* TEN (ТЭН) */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("waterSupply.ten")} icon={Zap}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("waterSupply.tenAutoMode")}>
                <Toggle
                  value={bool("watersupply_ihb_teh_automode")}
                  onChange={() => toggle("watersupply_ihb_teh_automode")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.tenDelay")}>
                <TempSlider
                  value={num("watersupply_ihb_teh_heating_delay", "120")}
                  min={1}
                  max={240}
                  unit=" мин"
                  onChange={(v) => set("watersupply_ihb_teh_heating_delay", v)}
                  disabled={!bool("watersupply_ihb_teh_automode")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.tenPower")}>
                <Toggle
                  value={bool("watersupply_ihb_teh_power")}
                  onChange={() => toggle("watersupply_ihb_teh_power")}
                  disabled={bool("watersupply_ihb_teh_automode")}
                />
              </SettingRow>
            </div>
            {bool("watersupply_ihb_teh_automode") && (
              <p className="mt-2 text-xs text-gray-500">
                {t("waterSupply.tenAutoHint")}
              </p>
            )}
          </CollapsibleSection>
        </section>

        {/* Anti-legionella */}
        <section className="bg-white rounded-lg shadow p-4">
          <CollapsibleSection title={t("waterSupply.antiLegionella")} icon={ShieldCheck}>
            <div className="divide-y divide-gray-100">
              <SettingRow label={t("waterSupply.almEnabled")}>
                <Toggle
                  value={almEnabled}
                  onChange={() => toggle("watersupply_ihb_alm_mode")}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.almTemp")}>
                <TempSlider
                  value={num("watersupply_alm_temp", "60")}
                  min={55}
                  max={70}
                  onChange={(v) => set("watersupply_alm_temp", v)}
                  disabled={!almEnabled}
                />
              </SettingRow>
              <div className="py-2">
                <span className="text-sm text-gray-600 block mb-2">
                  {t("waterSupply.almDays")}
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {DAYS.map((d) => (
                    <button
                      key={d.key}
                      disabled={!almEnabled}
                      onClick={() => toggleDay(d.key)}
                      className={`w-9 h-9 rounded-lg text-xs font-medium transition-colors disabled:opacity-50 ${
                        almDays.includes(d.key)
                          ? "bg-primary-600 text-white"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {d.label}
                    </button>
                  ))}
                </div>
              </div>
              <SettingRow label={t("waterSupply.almStartTime")}>
                <TimeInput
                  value={s("watersupply_alm_start_time", "03:00")}
                  onChange={(v) => set("watersupply_alm_start_time", v)}
                  disabled={!almEnabled}
                />
              </SettingRow>
              <SettingRow label={t("waterSupply.almDuration")}>
                <TempSlider
                  value={num("watersupply_alm_duration", "30")}
                  min={10}
                  max={120}
                  unit=" мин"
                  onChange={(v) => set("watersupply_alm_duration", v)}
                  disabled={!almEnabled}
                />
              </SettingRow>
            </div>
          </CollapsibleSection>
        </section>
      </div>
    </div>
  );
}
