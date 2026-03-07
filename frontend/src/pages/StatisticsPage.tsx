import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import {
  Thermometer,
  Droplets,
  Gauge,
  Flame,
  Heater,
  Waves,
} from "lucide-react";
import api from "@/api/client";
import { useDashboard } from "@/hooks/useDashboard";
import { fmt } from "@/lib/utils";
import CollapsibleSection from "@/components/CollapsibleSection";

/* ------------------------------------------------------------------ */
/*  Types                                                             */
/* ------------------------------------------------------------------ */

interface ChartData {
  labels: string[];
  datasets: { label: string; data: (number | null)[] }[];
}

type Period = "24h" | "7d" | "30d" | "90d";

const PERIODS: { key: Period; label: string; days: number }[] = [
  { key: "24h", label: "24 часа", days: 1 },
  { key: "7d", label: "7 дней", days: 7 },
  { key: "30d", label: "30 дней", days: 30 },
  { key: "90d", label: "90 дней", days: 90 },
];

const COLORS = [
  "#2563eb", "#16a34a", "#d97706", "#dc2626",
  "#7c3aed", "#0891b2", "#be185d", "#65a30d",
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function periodDates(period: Period) {
  const end = new Date();
  const start = new Date();
  const days = PERIODS.find((p) => p.key === period)!.days;
  start.setDate(start.getDate() - days);
  return {
    start: start.toISOString(),
    end: end.toISOString(),
  };
}

function formatLabel(label: string, period: Period): string {
  try {
    const d = new Date(label);
    if (period === "24h") {
      return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    }
    if (period === "7d") {
      return d.toLocaleDateString("ru-RU", { weekday: "short", day: "numeric" });
    }
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  } catch {
    return label;
  }
}

/* ------------------------------------------------------------------ */
/*  Chart component                                                   */
/* ------------------------------------------------------------------ */

function SensorChart({
  type,
  title,
  unit,
  icon: Icon,
  period,
  area,
}: {
  type: string;
  title: string;
  unit: string;
  icon: typeof Thermometer;
  period: Period;
  area?: boolean;
}) {
  const { t } = useTranslation();
  const { start, end } = periodDates(period);

  const { data, isLoading } = useQuery<ChartData>({
    queryKey: ["chart", type, period],
    queryFn: async () => {
      const { data } = await api.get(`/charts/${type}`, {
        params: { start, end },
      });
      return data;
    },
    refetchInterval: 60_000,
  });

  if (isLoading) {
    return (
      <div className="bg-white rounded-lg shadow p-4 animate-pulse">
        <div className="h-5 w-32 bg-gray-200 rounded mb-4" />
        <div className="h-48 bg-gray-100 rounded" />
      </div>
    );
  }

  if (!data || data.labels.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center gap-2 mb-3">
          <Icon className="h-5 w-5 text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
        </div>
        <p className="text-sm text-gray-400 py-8 text-center">
          {t("statistics.noData")}
        </p>
      </div>
    );
  }

  const chartData = data.labels.map((label, i) => ({
    name: formatLabel(label, period),
    ...Object.fromEntries(
      data.datasets.map((ds) => [ds.label, ds.data[i]]),
    ),
  }));

  const Chart = area ? AreaChart : LineChart;

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="h-5 w-5 text-gray-400" />
        <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
        <span className="ml-auto text-xs text-gray-400">
          {data.datasets.length} {data.datasets.length === 1 ? "датчик" : "датчиков"}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <Chart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="name"
            tick={{ fontSize: 10 }}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fontSize: 10 }}
            width={45}
            tickFormatter={(v) => `${v}${unit}`}
          />
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8 }}
            formatter={(v: number) => [`${fmt(v)}${unit}`, ""]}
          />
          <Legend
            wrapperStyle={{ fontSize: 11 }}
            iconType="circle"
            iconSize={8}
          />
          {data.datasets.map((ds, i) =>
            area ? (
              <Area
                key={ds.label}
                type="monotone"
                dataKey={ds.label}
                stroke={COLORS[i % COLORS.length]}
                fill={COLORS[i % COLORS.length]}
                fillOpacity={0.1}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ) : (
              <Line
                key={ds.label}
                type="monotone"
                dataKey={ds.label}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2}
                dot={false}
                connectNulls
              />
            ),
          )}
        </Chart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Stats summary cards                                               */
/* ------------------------------------------------------------------ */

function StatCard({
  label,
  value,
  unit,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  unit: string;
  icon: typeof Thermometer;
  color: string;
}) {
  return (
    <div className="rounded-lg border border-gray-100 bg-white p-4 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`h-4 w-4 ${color}`} />
        <span className="text-xs text-gray-500">{label}</span>
      </div>
      <span className="text-2xl font-bold text-gray-800">
        {fmt(value)}
        <span className="text-sm font-normal text-gray-400 ml-1">{unit}</span>
      </span>
    </div>
  );
}

/* ================================================================== */
/*  Main page                                                         */
/* ================================================================== */

export default function StatisticsPage() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<Period>("7d");
  const { data: dashboard } = useDashboard();

  const stats = dashboard?.stats;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-gray-800">{t("statistics.title")}</h2>

        {/* Period selector */}
        <div className="flex gap-1.5 bg-gray-100 rounded-lg p-1">
          {PERIODS.map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                period === p.key
                  ? "bg-white text-gray-800 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* 24h summary cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label={t("statistics.boilerHours")}
            value={stats.whk24}
            unit="ч"
            icon={Flame}
            color="text-red-500"
          />
          <StatCard
            label={t("statistics.radiatorHours")}
            value={stats.whr24}
            unit="ч"
            icon={Heater}
            color="text-orange-500"
          />
          <StatCard
            label={t("statistics.floorHours")}
            value={stats.whf24}
            unit="ч"
            icon={Waves}
            color="text-amber-500"
          />
          <StatCard
            label={t("statistics.ihbHours")}
            value={stats.whb24}
            unit="ч"
            icon={Droplets}
            color="text-blue-500"
          />
        </div>
      )}

      {/* Climate charts */}
      <CollapsibleSection title={t("statistics.climate")} icon={Thermometer}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <SensorChart
            type="ChartTemperature"
            title={t("statistics.temperatureChart")}
            unit="°"
            icon={Thermometer}
            period={period}
            area
          />
          <SensorChart
            type="ChartHumidity"
            title={t("statistics.humidityChart")}
            unit="%"
            icon={Droplets}
            period={period}
            area
          />
        </div>
      </CollapsibleSection>

      {/* Heating charts */}
      <CollapsibleSection title={t("statistics.heatingCharts")} icon={Flame}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <SensorChart
            type="ChartPressure"
            title={t("statistics.pressureChart")}
            unit=" бар"
            icon={Gauge}
            period={period}
          />
          <SensorChart
            type="ChartHeating"
            title={t("statistics.heatingTempChart")}
            unit="°"
            icon={Flame}
            period={period}
          />
        </div>
      </CollapsibleSection>
    </div>
  );
}
