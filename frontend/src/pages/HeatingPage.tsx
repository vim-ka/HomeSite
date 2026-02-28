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
} from "recharts";
import api from "@/api/client";
import { useDashboard } from "@/hooks/useDashboard";
import { useSettingUpdate } from "@/hooks/useSettingUpdate";
import { PZA_CURVES, interpolatePZA } from "@/lib/pzaCurves";
import { fmt } from "@/lib/utils";

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

  const { data: pzaChart } = useQuery({
    queryKey: ["chart", "ChartRadiators"],
    queryFn: async () => {
      const { data } = await api.get("/charts/ChartRadiators");
      return data;
    },
  });

  const [selectedCurve, setSelectedCurve] = useState(0);

  const boilerTemp = settings?.heating_boiler_temp ?? "50";
  const boilerPower = settings?.heating_boiler_power ?? "0";

  // Build PZA chart data
  const pzaData = PZA_CURVES[0]!.points.map((p) => {
    const row: Record<string, number> = { outdoor: p.outdoor };
    PZA_CURVES.forEach((curve, i) => {
      row[`curve${i + 1}`] = interpolatePZA(curve, p.outdoor);
    });
    return row;
  });

  const COLORS = ["#2563eb", "#16a34a", "#d97706", "#dc2626", "#7c3aed"];

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("heating.title")}</h2>

      {/* Boiler Control */}
      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">{t("heating.boiler")}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">
              {t("heating.boilerTemp")}: {boilerTemp}°C
            </label>
            <input
              type="range"
              min="30"
              max="80"
              value={boilerTemp}
              onChange={(e) => update({ heating_boiler_temp: e.target.value })}
              className="w-full"
            />
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-600">{t("heating.boilerPower")}</label>
            <button
              onClick={() =>
                update({
                  heating_boiler_power: boilerPower === "1" ? "0" : "1",
                })
              }
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                boilerPower === "1"
                  ? "bg-green-500 text-white hover:bg-green-600"
                  : "bg-gray-200 text-gray-600 hover:bg-gray-300"
              }`}
            >
              {boilerPower === "1" ? t("dashboard.on") : t("dashboard.off")}
            </button>
          </div>
        </div>
      </section>

      {/* Heating Circuits Status */}
      {dashboard?.heating && dashboard.heating.length > 0 && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-3">Контуры отопления</h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {dashboard.heating.map((c) => (
              <div key={c.circuit} className="border rounded-lg p-3">
                <p className="font-medium text-gray-800">{c.circuit}</p>
                <div className="mt-2 space-y-1 text-sm text-gray-600">
                  <p>Уставка: <span className="font-medium text-gray-800">{fmt(c.temp_set)}°C</span></p>
                  <p>Подача: <span className="font-medium text-gray-800">{fmt(c.temp_supply)}°C</span></p>
                  <p>Обратка: <span className="font-medium text-gray-800">{fmt(c.temp_return)}°C</span></p>
                  {c.pressure != null && (
                    <p>Давление: <span className="font-medium text-gray-800">{fmt(c.pressure)} бар</span></p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* PZA Curves Chart */}
      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("heating.pzaCurve")}</h3>
        <div className="flex gap-2 mb-3">
          {PZA_CURVES.map((curve, i) => (
            <button
              key={i}
              onClick={() => setSelectedCurve(i)}
              className={`px-3 py-1 text-xs rounded-full transition-colors ${
                selectedCurve === i
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
            >
              {curve.name}
            </button>
          ))}
        </div>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={pzaData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="outdoor" label={{ value: t("heating.outdoorTemp"), position: "bottom" }} />
            <YAxis label={{ value: "°C", angle: -90, position: "insideLeft" }} />
            <Tooltip />
            <Legend />
            {PZA_CURVES.map((curve, i) => (
              <Line
                key={i}
                type="monotone"
                dataKey={`curve${i + 1}`}
                name={curve.name}
                stroke={COLORS[i]}
                strokeWidth={selectedCurve === i ? 3 : 1}
                opacity={selectedCurve === i ? 1 : 0.3}
                dot={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </section>

      {/* Radiators Chart (from API) */}
      {pzaChart && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("heating.radiators")}</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart
              data={pzaChart.labels.map((label: string, i: number) => ({
                name: label,
                ...Object.fromEntries(
                  pzaChart.datasets.map((ds: { label: string; data: number[] }) => [
                    ds.label,
                    ds.data[i],
                  ]),
                ),
              }))}
            >
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis />
              <Tooltip />
              <Legend />
              {pzaChart.datasets.map((ds: { label: string }, i: number) => (
                <Line
                  key={ds.label}
                  type="monotone"
                  dataKey={ds.label}
                  stroke={COLORS[i % COLORS.length]}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </section>
      )}
    </div>
  );
}
