import { useTranslation } from "react-i18next";
import LoadingSpinner from "@/components/LoadingSpinner";
import {
  Thermometer,
  Droplets,
  Gauge,
  Sofa,
  CookingPot,
  Baby,
  BedDouble,
  Monitor,
  TreePine,
  Flame,
  Home,
  ArrowUpFromLine,
  ArrowDownToLine,
  Power,
  ShowerHead,
  type LucideIcon,
} from "lucide-react";
import { useDashboard } from "@/hooks/useDashboard";
import type { ClimateRoom, HeatingCircuit, WaterSupplyItem } from "@/hooks/useDashboard";
import { fmt, cn } from "@/lib/utils";
import CollapsibleSection from "@/components/CollapsibleSection";

const ROOM_ICONS: Record<string, LucideIcon> = {
  "Гостиная": Sofa,
  "Кухня": CookingPot,
  "Детская": Baby,
  "Спальня": BedDouble,
  "Кабинет": Monitor,
  "Улица": TreePine,
  "Котельная": Flame,
};

function ClimateCard({ room }: { room: ClimateRoom }) {
  const { t } = useTranslation();
  const RoomIcon = ROOM_ICONS[room.room] ?? Home;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* Room name + icon */}
      <div className="mb-4 flex items-center justify-between">
        <h4 className="text-lg font-semibold text-gray-800">{room.room}</h4>
        <RoomIcon className="h-5 w-5 text-gray-400" />
      </div>

      {/* Metrics */}
      <div className="space-y-3">
        {/* Temperature */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Thermometer className="h-4 w-4 text-orange-500" />
            <span>{t("dashboard.temperature")}</span>
          </div>
          <span className="text-xl font-bold text-orange-500">
            {room.temperature != null ? `${fmt(room.temperature)}°` : "—"}
          </span>
        </div>

        {/* Humidity */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Droplets className="h-4 w-4 text-sky-500" />
            <span>{t("dashboard.humidity")}</span>
          </div>
          <span className="text-xl font-bold text-sky-500">
            {room.humidity != null ? `${fmt(room.humidity)}%` : "—"}
          </span>
        </div>

        {/* Pressure */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Gauge className="h-4 w-4 text-emerald-500" />
            <span>{t("dashboard.pressure")}</span>
          </div>
          <span className="text-xl font-bold text-emerald-500">
            {room.pressure != null ? fmt(room.pressure) : "—"}
          </span>
        </div>
      </div>
    </div>
  );
}

function supplyGlow(actual: number | null, setpoint: number | null): string {
  if (actual == null || setpoint == null) return "font-semibold text-gray-700";
  if (actual > setpoint) return "font-bold temp-glow-red";
  if (actual < setpoint) return "font-bold temp-glow-blue";
  return "font-semibold text-gray-700";
}

function returnGlow(ret: number | null, supply: number | null): string {
  if (ret == null) return "font-semibold text-gray-700";
  if (supply != null && ret >= supply) return "font-bold temp-glow-red";
  return "font-bold text-blue-500";
}

function HeatingCard({ circuit: c }: { circuit: HeatingCircuit }) {
  const { t } = useTranslation();
  const pumpOn = c.pump === "1";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-lg font-semibold text-gray-800">{c.circuit}</h4>
        <Flame className="h-5 w-5 text-gray-400" />
      </div>

      {/* Set temp — prominent */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <span className="text-sm text-gray-500">{t("dashboard.tempSet")}</span>
          {c.pza_mode ? (
            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300">
              ПЗА кр.{c.pza_curve}
            </span>
          ) : c.pza_capable ? (
            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">
              Ручн.
            </span>
          ) : null}
        </div>
        <span className="text-2xl font-bold text-orange-500">
          {c.temp_set != null ? `${fmt(c.temp_set)}°` : "—"}
        </span>
      </div>

      {/* Supply / Return */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ArrowUpFromLine className="h-4 w-4 text-red-400" />
            <span>{t("dashboard.tempSupply")}</span>
          </div>
          <span className={cn("text-lg", supplyGlow(c.temp_supply, c.temp_set))}>
            {c.temp_supply != null ? `${fmt(c.temp_supply)}°` : "—"}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ArrowDownToLine className="h-4 w-4 text-blue-400" />
            <span>{t("dashboard.tempReturn")}</span>
          </div>
          <span className={cn("text-lg", returnGlow(c.temp_return, c.temp_supply))}>
            {c.temp_return != null ? `${fmt(c.temp_return)}°` : "—"}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Gauge className="h-4 w-4 text-emerald-500" />
            <span>{t("dashboard.pressure")}</span>
          </div>
          <span className="font-semibold text-gray-700">
            {c.pressure != null ? `${fmt(c.pressure)} бар` : "—"}
          </span>
        </div>

        {/* Pump status */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Power className="h-4 w-4 text-gray-400" />
            <span>{t("dashboard.pump")}</span>
          </div>
          <span
            className={cn(
              "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
              pumpOn
                ? "bg-green-100 text-green-700"
                : "bg-gray-100 text-gray-500",
            )}
          >
            {pumpOn ? t("dashboard.on") : t("dashboard.off")}
          </span>
        </div>
      </div>
    </div>
  );
}

function WaterCard({ item: w }: { item: WaterSupplyItem }) {
  const { t } = useTranslation();
  const pumpOn = w.pump === "1";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <h4 className="text-lg font-semibold text-gray-800">{w.type}</h4>
        <ShowerHead className="h-5 w-5 text-gray-400" />
      </div>

      <div className="space-y-2">
        {/* Temp Set */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Thermometer className="h-4 w-4 text-orange-500" />
            <span>{t("dashboard.tempSet")}</span>
          </div>
          <span className="text-xl font-bold text-orange-500">
            {w.temp_set != null ? `${fmt(w.temp_set)}°` : "—"}
          </span>
        </div>

        {/* Temp Fact */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Thermometer className="h-4 w-4 text-sky-500" />
            <span>{t("dashboard.temperature")}</span>
          </div>
          <span className={cn("text-xl", supplyGlow(w.temp_fact, w.temp_set))}>
            {w.temp_fact != null ? `${fmt(w.temp_fact)}°` : "—"}
          </span>
        </div>

        {/* Pump */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Power className="h-4 w-4 text-gray-400" />
            <span>{t("dashboard.pump")}</span>
          </div>
          <span
            className={cn(
              "inline-block rounded-full px-2.5 py-0.5 text-xs font-medium",
              pumpOn
                ? "bg-green-100 text-green-700"
                : "bg-gray-100 text-gray-500",
            )}
          >
            {pumpOn ? t("dashboard.on") : t("dashboard.off")}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useDashboard();

  if (isLoading) return <LoadingSpinner />;
  if (error) return <p className="text-red-600">{t("common.error")}: {String(error)}</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("dashboard.title")}</h2>

      {/* Climate */}
      <CollapsibleSection title={t("dashboard.climate")} icon={Thermometer}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data.climate.map((room) => (
            <ClimateCard key={room.room} room={room} />
          ))}
        </div>
      </CollapsibleSection>

      {/* Heating */}
      <CollapsibleSection title={t("dashboard.heating")} icon={Flame}>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {data.heating.map((c) => (
            <HeatingCard key={c.circuit} circuit={c} />
          ))}
        </div>
      </CollapsibleSection>

      {/* Water Supply */}
      <CollapsibleSection title={t("dashboard.waterSupply")} icon={Droplets}>
        {data.water_supply.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {data.water_supply.map((w) => (
              <WaterCard key={w.type} item={w} />
            ))}
          </div>
        ) : (
          <p className="text-gray-500 text-sm">{t("dashboard.noData")}</p>
        )}
      </CollapsibleSection>

    </div>
  );
}
