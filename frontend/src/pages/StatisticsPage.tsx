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
} from "recharts";
import api from "@/api/client";

interface ChartData {
  labels: string[];
  datasets: { label: string; data: number[] }[];
}

const CHART_CONFIGS = [
  { type: "ChartTemperature", titleKey: "statistics.temperatureChart", unit: "°C" },
  { type: "ChartPressure", titleKey: "statistics.pressureChart", unit: "бар" },
  { type: "ChartHumidity", titleKey: "statistics.humidityChart", unit: "%" },
] as const;

const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed", "#0891b2"];

function SensorChart({ type, title, unit }: { type: string; title: string; unit: string }) {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery<ChartData>({
    queryKey: ["chart", type],
    queryFn: async () => {
      const { data } = await api.get(`/charts/${type}`);
      return data;
    },
    refetchInterval: 60_000,
  });

  if (isLoading) return <p className="text-gray-400 text-sm">{t("common.loading")}</p>;
  if (!data || data.labels.length === 0) return null;

  const chartData = data.labels.map((label, i) => ({
    name: label,
    ...Object.fromEntries(
      data.datasets.map((ds) => [ds.label, ds.data[i]]),
    ),
  }));

  return (
    <section className="bg-white rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold text-gray-700 mb-3">{title}</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" tick={{ fontSize: 11 }} />
          <YAxis unit={unit} />
          <Tooltip />
          <Legend />
          {data.datasets.map((ds, i) => (
            <Line
              key={ds.label}
              type="monotone"
              dataKey={ds.label}
              stroke={COLORS[i % COLORS.length]}
              dot={false}
              strokeWidth={2}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </section>
  );
}

export default function StatisticsPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("statistics.title")}</h2>
      {CHART_CONFIGS.map((cfg) => (
        <SensorChart
          key={cfg.type}
          type={cfg.type}
          title={t(cfg.titleKey)}
          unit={cfg.unit}
        />
      ))}
    </div>
  );
}
