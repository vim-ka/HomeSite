import { useEffect, useState } from "react";
import {
  ScrollView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Dimensions,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import api from "../../src/api/client";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";
import LineChart from "../../src/components/LineChart";
import { useTheme } from "../../src/hooks/useTheme";

type Period = "24h" | "7d" | "30d" | "90d";

const PERIODS: { key: Period; label: string }[] = [
  { key: "24h", label: "24ч" },
  { key: "7d", label: "7д" },
  { key: "30d", label: "30д" },
  { key: "90d", label: "90д" },
];

const SERIES_COLORS = [
  "#2563eb", "#16a34a", "#d97706", "#dc2626",
  "#7c3aed", "#0891b2", "#be185d", "#65a30d",
];

const screenWidth = Dimensions.get("window").width;
const CHART_WIDTH = screenWidth - 32 - 24; // minus page padding (16+16) and card padding (12+12)

interface ChartResponse {
  labels: string[];
  datasets: { label: string; data: (number | null)[] }[];
}

function formatLabel(raw: string, period: Period): string {
  try {
    const d = new Date(raw.endsWith("Z") ? raw : raw + "Z");
    if (period === "24h") {
      return d.toLocaleTimeString("ru-RU", { hour: "2-digit", minute: "2-digit" });
    }
    if (period === "7d") {
      return d.toLocaleDateString("ru-RU", { weekday: "short", day: "numeric" });
    }
    return d.toLocaleDateString("ru-RU", { day: "numeric", month: "short" });
  } catch {
    return raw;
  }
}

function SensorChart({
  chartType,
  title,
  unit,
  period,
}: {
  chartType: string;
  title: string;
  unit: string;
  period: Period;
}) {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});

  const periodToRange = (p: Period) => {
    const end = new Date();
    const start = new Date();
    if (p === "24h") start.setHours(end.getHours() - 24);
    else if (p === "7d") start.setDate(end.getDate() - 7);
    else if (p === "30d") start.setDate(end.getDate() - 30);
    else start.setDate(end.getDate() - 90);
    return { start: start.toISOString(), end: end.toISOString() };
  };
  const { start, end } = periodToRange(period);

  const { data, isLoading } = useQuery<ChartResponse>({
    queryKey: ["charts", chartType, period],
    queryFn: async () => {
      const { data } = await api.get(`/charts/${chartType}?start=${start}&end=${end}`);
      return data;
    },
  });

  // Enable first dataset by default
  useEffect(() => {
    if (data?.datasets?.length && Object.keys(enabled).length === 0) {
      setEnabled({ [data.datasets[0].label]: true });
    }
  }, [data]);

  if (isLoading) {
    return (
      <Card style={styles.chartCard}>
        <Text style={[styles.chartTitle, { color: colors.gray[700] }]}>{title}</Text>
        <Text style={[styles.noData, { color: colors.gray[400] }]}>{t("common.loading")}</Text>
      </Card>
    );
  }

  if (!data || data.labels.length === 0) {
    return (
      <Card style={styles.chartCard}>
        <Text style={[styles.chartTitle, { color: colors.gray[700] }]}>{title}</Text>
        <Text style={[styles.noData, { color: colors.gray[400] }]}>{t("statistics.noData")}</Text>
      </Card>
    );
  }

  const visibleDatasets = data.datasets
    .map((ds, i) => ({
      label: ds.label,
      data: ds.data,
      color: SERIES_COLORS[i % SERIES_COLORS.length],
    }))
    .filter((ds) => enabled[ds.label]);

  const xLabels = data.labels.map((l) => formatLabel(l, period));

  return (
    <Card style={styles.chartCard}>
      <Text style={[styles.chartTitle, { color: colors.gray[700] }]}>{title}</Text>

      {/* Sensor toggles */}
      <View style={styles.legendRow}>
        {data.datasets.map((ds, i) => {
          const active = !!enabled[ds.label];
          const color = SERIES_COLORS[i % SERIES_COLORS.length];
          return (
            <TouchableOpacity
              key={ds.label}
              style={[
                styles.legendBtn,
                { borderColor: colors.gray[200] },
                active && { backgroundColor: color + "22", borderColor: color },
              ]}
              onPress={() =>
                setEnabled((prev) => ({ ...prev, [ds.label]: !prev[ds.label] }))
              }
            >
              <View style={[styles.legendDot, { backgroundColor: color }]} />
              <Text style={[styles.legendText, { color: colors.gray[700] }]} numberOfLines={1}>
                {ds.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {visibleDatasets.length > 0 ? (
        <LineChart
          labels={xLabels}
          datasets={visibleDatasets}
          unit={unit}
          width={CHART_WIDTH}
          height={200}
        />
      ) : (
        <Text style={[styles.noData, { color: colors.gray[400] }]}>—</Text>
      )}
    </Card>
  );
}

export default function StatsScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const [period, setPeriod] = useState<Period>("24h");

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.gray[100] }]}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={false} onRefresh={() => {}} />}
    >
      {/* Period selector */}
      <View style={[styles.periodRow, { backgroundColor: colors.white, borderColor: colors.gray[200] }]}>
        {PERIODS.map((p) => (
          <TouchableOpacity
            key={p.key}
            style={[styles.periodBtn, period === p.key && { backgroundColor: colors.primary[600] }]}
            onPress={() => setPeriod(p.key)}
          >
            <Text style={[styles.periodText, { color: colors.gray[500] }, period === p.key && { color: "#ffffff" }]}>
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Climate */}
      <Section title={t("statistics.climate")}>
        <SensorChart
          chartType="ChartTemperature"
          title={t("dashboard.temperature")}
          unit="°"
          period={period}
        />
        <SensorChart
          chartType="ChartHumidity"
          title={t("dashboard.humidity")}
          unit="%"
          period={period}
        />
        <SensorChart
          chartType="ChartPressureAtmo"
          title={t("statistics.pressureAtmo")}
          unit=" гПа"
          period={period}
        />
      </Section>

      {/* Heating */}
      <Section title={t("statistics.heatingCharts")}>
        <SensorChart
          chartType="ChartPressureSystem"
          title={t("statistics.pressureSystem")}
          unit=" бар"
          period={period}
        />
        <SensorChart
          chartType="ChartHeating"
          title={t("heating.title")}
          unit="°"
          period={period}
        />
      </Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  periodRow: {
    flexDirection: "row",
    borderRadius: 12,
    padding: 4,
    marginBottom: 20,
    borderWidth: 1,
  },
  periodBtn: {
    flex: 1,
    paddingVertical: 10,
    alignItems: "center",
    borderRadius: 10,
  },
  periodText: { fontSize: 14, fontWeight: "600" },
  chartCard: { marginBottom: 12 },
  chartTitle: { fontSize: 13, fontWeight: "700", marginBottom: 8 },
  legendRow: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginBottom: 8 },
  legendBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 16,
    borderWidth: 1,
    maxWidth: "48%",
  },
  legendDot: { width: 8, height: 8, borderRadius: 4 },
  legendText: { fontSize: 11, fontWeight: "500" },
  noData: { fontSize: 14, textAlign: "center", paddingVertical: 20 },
});
