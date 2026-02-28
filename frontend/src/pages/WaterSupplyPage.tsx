import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import { useDashboard } from "@/hooks/useDashboard";
import { useSettingUpdate } from "@/hooks/useSettingUpdate";
import { fmt } from "@/lib/utils";

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

  const ihbTemp = settings?.watersupply_ihb_temp ?? "45";
  const coldPump = settings?.watersupply_pump ?? "0";
  const hotPump = settings?.watersupply_pump_hot ?? "0";
  const autoMode = settings?.watersupply_automode ?? "0";

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-bold text-gray-800">{t("waterSupply.title")}</h2>

      {/* IHB Control */}
      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">{t("waterSupply.ihb")}</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">
              {t("waterSupply.ihbTemp")}: {ihbTemp}°C
            </label>
            <input
              type="range"
              min="30"
              max="70"
              value={ihbTemp}
              onChange={(e) => update({ watersupply_ihb_temp: e.target.value })}
              className="w-full"
            />
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm text-gray-600">{t("heating.autoMode")}</label>
            <button
              onClick={() =>
                update({ watersupply_automode: autoMode === "1" ? "0" : "1" })
              }
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                autoMode === "1"
                  ? "bg-green-500 text-white hover:bg-green-600"
                  : "bg-gray-200 text-gray-600 hover:bg-gray-300"
              }`}
            >
              {autoMode === "1" ? t("dashboard.on") : t("dashboard.off")}
            </button>
          </div>
        </div>
      </section>

      {/* Pumps */}
      <section className="bg-white rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-700 mb-4">Насосы</h3>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">{t("waterSupply.coldPump")}</span>
            <button
              onClick={() =>
                update({ watersupply_pump: coldPump === "1" ? "0" : "1" })
              }
              disabled={autoMode === "1"}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                coldPump === "1"
                  ? "bg-green-500 text-white hover:bg-green-600"
                  : "bg-gray-200 text-gray-600 hover:bg-gray-300"
              }`}
            >
              {coldPump === "1" ? t("dashboard.on") : t("dashboard.off")}
            </button>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-600">{t("waterSupply.hotPump")}</span>
            <button
              onClick={() =>
                update({ watersupply_pump_hot: hotPump === "1" ? "0" : "1" })
              }
              disabled={autoMode === "1"}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                hotPump === "1"
                  ? "bg-green-500 text-white hover:bg-green-600"
                  : "bg-gray-200 text-gray-600 hover:bg-gray-300"
              }`}
            >
              {hotPump === "1" ? t("dashboard.on") : t("dashboard.off")}
            </button>
          </div>
        </div>
        {autoMode === "1" && (
          <p className="text-xs text-amber-600 mt-2">
            Ручное управление насосами отключено в автоматическом режиме
          </p>
        )}
      </section>

      {/* Water Supply Status */}
      {dashboard?.water_supply && dashboard.water_supply.length > 0 && (
        <section className="bg-white rounded-lg shadow p-4">
          <h3 className="text-lg font-semibold text-gray-700 mb-3">Текущие показания</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-4 py-2 text-left">Точка</th>
                  <th className="px-4 py-2 text-right">Уставка</th>
                  <th className="px-4 py-2 text-right">Факт</th>
                  <th className="px-4 py-2 text-center">Насос</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {dashboard.water_supply.map((w) => (
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
        </section>
      )}
    </div>
  );
}
