import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import { fmtTime } from "@/lib/utils";

interface EventLog {
  id: number;
  timestamp: string;
  level: string;
  source: string;
  method: string;
  path: string;
  message: string | null;
  payload: string | null;
}

interface PaginatedEvents {
  items: EventLog[];
  total: number;
  page: number;
  per_page: number;
}

const LEVEL_STYLES: Record<string, string> = {
  INFO: "bg-blue-100 text-blue-700",
  WARNING: "bg-amber-100 text-amber-700",
  ERROR: "bg-red-100 text-red-700",
  DEBUG: "bg-gray-100 text-gray-500",
};

export default function EventsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(1);
  const [levelFilter, setLevelFilter] = useState("");

  const { data, isLoading } = useQuery<PaginatedEvents>({
    queryKey: ["events", page, levelFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(page), per_page: "20" });
      if (levelFilter) params.set("level", levelFilter);
      const { data } = await api.get(`/events?${params}`);
      return data;
    },
    placeholderData: (prev) => prev,
  });

  const handleExport = async () => {
    try {
      const { data } = await api.get("/events/export/csv", { responseType: "blob" });
      const url = URL.createObjectURL(data);
      const a = document.createElement("a");
      a.href = url;
      a.download = "events.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // ignore
    }
  };

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-gray-800">{t("events.title")}</h2>
        <button
          onClick={handleExport}
          className="px-4 py-2 bg-primary-600 text-white text-sm rounded-lg hover:bg-primary-700 transition-colors"
        >
          {t("events.export")}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        {["", "INFO", "WARNING", "ERROR"].map((level) => (
          <button
            key={level}
            onClick={() => { setLevelFilter(level); setPage(1); }}
            className={`px-3 py-1 text-xs rounded-full transition-colors ${
              levelFilter === level
                ? "bg-primary-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {level || "Все"}
          </button>
        ))}
      </div>

      {/* Table */}
      {isLoading ? (
        <p className="text-gray-500">{t("common.loading")}</p>
      ) : !data || data.items.length === 0 ? (
        <p className="text-gray-500">{t("events.noEvents")}</p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-sm bg-white rounded-lg shadow">
              <thead className="bg-gray-50 text-gray-600">
                <tr>
                  <th className="px-3 py-2 text-left">{t("events.timestamp")}</th>
                  <th className="px-3 py-2 text-center">{t("events.level")}</th>
                  <th className="px-3 py-2 text-left">{t("events.source")}</th>
                  <th className="px-3 py-2 text-left">{t("events.message")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.items.map((ev) => (
                  <tr key={ev.id} className="hover:bg-gray-50">
                    <td className="px-3 py-2 whitespace-nowrap text-xs text-gray-500">
                      {fmtTime(ev.timestamp)}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${
                          LEVEL_STYLES[ev.level] ?? "bg-gray-100 text-gray-500"
                        }`}
                      >
                        {ev.level}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs">
                      {ev.method} {ev.path}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-600 max-w-md truncate">
                      {ev.message || ev.payload || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="flex justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
            >
              &larr;
            </button>
            <span className="px-3 py-1 text-sm text-gray-600">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200 disabled:opacity-50"
            >
              &rarr;
            </button>
          </div>
        </>
      )}
    </div>
  );
}
