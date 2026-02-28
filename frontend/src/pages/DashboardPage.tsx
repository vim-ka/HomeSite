import { useTranslation } from "react-i18next";
import { useDashboard } from "@/hooks/useDashboard";
import { fmt } from "@/lib/utils";

export default function DashboardPage() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useDashboard();

  if (isLoading) return <p className="text-gray-500">{t("common.loading")}</p>;
  if (error) return <p className="text-red-600">{t("common.error")}: {String(error)}</p>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("dashboard.title")}</h2>

      {/* Climate */}
      <section>
        <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("dashboard.climate")}</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm bg-white rounded-lg shadow">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 text-left">{t("dashboard.room")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.temperature")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.humidity")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.pressure")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.climate.map((room) => (
                <tr key={room.room} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{room.room}</td>
                  <td className="px-4 py-2 text-right">{fmt(room.temperature)}°C</td>
                  <td className="px-4 py-2 text-right">{fmt(room.humidity)}%</td>
                  <td className="px-4 py-2 text-right">{fmt(room.pressure)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Heating */}
      <section>
        <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("dashboard.heating")}</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm bg-white rounded-lg shadow">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="px-4 py-2 text-left">{t("dashboard.circuit")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.tempSet")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.tempSupply")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.tempReturn")}</th>
                <th className="px-4 py-2 text-right">{t("dashboard.pressure")}</th>
                <th className="px-4 py-2 text-center">{t("dashboard.pump")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.heating.map((c) => (
                <tr key={c.circuit} className="hover:bg-gray-50">
                  <td className="px-4 py-2 font-medium">{c.circuit}</td>
                  <td className="px-4 py-2 text-right">{fmt(c.temp_set)}°C</td>
                  <td className="px-4 py-2 text-right">{fmt(c.temp_supply)}°C</td>
                  <td className="px-4 py-2 text-right">{fmt(c.temp_return)}°C</td>
                  <td className="px-4 py-2 text-right">{fmt(c.pressure)} бар</td>
                  <td className="px-4 py-2 text-center">
                    <span
                      className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                        c.pump === "1"
                          ? "bg-green-100 text-green-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {c.pump === "1" ? t("dashboard.on") : t("dashboard.off")}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Water Supply */}
      <section>
        <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("dashboard.waterSupply")}</h3>
        {data.water_supply.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm bg-white rounded-lg shadow">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-4 py-2 text-left">Тип</th>
                  <th className="px-4 py-2 text-right">{t("dashboard.tempSet")}</th>
                  <th className="px-4 py-2 text-right">{t("dashboard.temperature")}</th>
                  <th className="px-4 py-2 text-center">{t("dashboard.pump")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.water_supply.map((w) => (
                  <tr key={w.type} className="hover:bg-gray-50">
                    <td className="px-4 py-2 font-medium">{w.type}</td>
                    <td className="px-4 py-2 text-right">{fmt(w.tempSet)}°C</td>
                    <td className="px-4 py-2 text-right">{fmt(w.tempFact)}°C</td>
                    <td className="px-4 py-2 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          w.Pump === "1"
                            ? "bg-green-100 text-green-700"
                            : "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {w.Pump === "1" ? t("dashboard.on") : t("dashboard.off")}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-500 text-sm">{t("dashboard.noData")}</p>
        )}
      </section>

      {/* 24h Stats */}
      <section>
        <h3 className="text-lg font-semibold text-gray-700 mb-3">{t("dashboard.stats24h")}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-white rounded-lg shadow p-4 text-center">
            <p className="text-sm text-gray-500">Работа отопления</p>
            <p className="text-2xl font-bold text-primary-700">
              {fmt(data.stats.heating_hours)} ч
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4 text-center">
            <p className="text-sm text-gray-500">Ср. температура</p>
            <p className="text-2xl font-bold text-primary-700">
              {fmt(data.stats.climate_avg_temp)}°C
            </p>
          </div>
          <div className="bg-white rounded-lg shadow p-4 text-center">
            <p className="text-sm text-gray-500">Ср. влажность</p>
            <p className="text-2xl font-bold text-primary-700">
              {fmt(data.stats.climate_avg_humidity)}%
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
