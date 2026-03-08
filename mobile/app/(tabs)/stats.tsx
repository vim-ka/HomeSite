import { useState } from "react";
import { ScrollView, View, Text, TouchableOpacity, StyleSheet, RefreshControl, Dimensions } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import api from "../../src/api/client";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";
import { colors } from "../../src/theme/colors";

type Period = "24h" | "7d" | "30d" | "90d";

interface ChartPoint {
  timestamp: string;
  value: number;
  label?: string;
}

interface ChartSeries {
  sensor_name: string;
  data: ChartPoint[];
}

const PERIODS: { key: Period; label: string }[] = [
  { key: "24h", label: "24ч" },
  { key: "7d", label: "7д" },
  { key: "30d", label: "30д" },
  { key: "90d", label: "90д" },
];

const screenWidth = Dimensions.get("window").width;

// Simple bar/sparkline renderer (no heavy chart lib)
function MiniChart({ data, color, height = 60 }: { data: number[]; color: string; height?: number }) {
  if (data.length === 0) return null;
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const barWidth = Math.max(2, (screenWidth - 80) / data.length - 1);

  return (
    <View style={[styles.chartContainer, { height }]}>
      <View style={styles.chartBars}>
        {data.map((v, i) => (
          <View
            key={i}
            style={{
              width: barWidth,
              height: Math.max(2, ((v - min) / range) * (height - 10)),
              backgroundColor: color,
              borderRadius: 1,
              marginRight: 1,
            }}
          />
        ))}
      </View>
      <View style={styles.chartLabels}>
        <Text style={styles.chartLabel}>{min.toFixed(1)}</Text>
        <Text style={styles.chartLabel}>{max.toFixed(1)}</Text>
      </View>
    </View>
  );
}

export default function StatsScreen() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<Period>("24h");

  const { data: climateData, isLoading, refetch } = useQuery<ChartSeries[]>({
    queryKey: ["charts", "climate", period],
    queryFn: async () => {
      const { data } = await api.get(`/charts/climate?period=${period}`);
      return data;
    },
  });

  const { data: heatingData } = useQuery<ChartSeries[]>({
    queryKey: ["charts", "heating", period],
    queryFn: async () => {
      const { data } = await api.get(`/charts/heating?period=${period}`);
      return data;
    },
  });

  const { data: pressureData } = useQuery<ChartSeries[]>({
    queryKey: ["charts", "pressure", period],
    queryFn: async () => {
      const { data } = await api.get(`/charts/pressure?period=${period}`);
      return data;
    },
  });

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={refetch} />}
    >
      {/* Period selector */}
      <View style={styles.periodRow}>
        {PERIODS.map((p) => (
          <TouchableOpacity
            key={p.key}
            style={[styles.periodBtn, period === p.key && styles.periodBtnActive]}
            onPress={() => setPeriod(p.key)}
          >
            <Text style={[styles.periodText, period === p.key && styles.periodTextActive]}>
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Climate */}
      <Section title={t("statistics.climate")}>
        {climateData && climateData.length > 0 ? (
          climateData.map((series) => (
            <Card key={series.sensor_name} style={styles.chartCard}>
              <Text style={styles.chartTitle}>{series.sensor_name}</Text>
              <MiniChart
                data={series.data.map((d) => d.value)}
                color={colors.orange[500]}
              />
            </Card>
          ))
        ) : (
          <Text style={styles.noData}>{t("statistics.noData")}</Text>
        )}
      </Section>

      {/* Heating */}
      <Section title={t("statistics.heatingCharts")}>
        {heatingData && heatingData.length > 0 ? (
          heatingData.map((series) => (
            <Card key={series.sensor_name} style={styles.chartCard}>
              <Text style={styles.chartTitle}>{series.sensor_name}</Text>
              <MiniChart
                data={series.data.map((d) => d.value)}
                color={colors.red[500]}
              />
            </Card>
          ))
        ) : (
          <Text style={styles.noData}>{t("statistics.noData")}</Text>
        )}
      </Section>

      {/* Pressure */}
      <Section title={t("dashboard.pressure")}>
        {pressureData && pressureData.length > 0 ? (
          pressureData.map((series) => (
            <Card key={series.sensor_name} style={styles.chartCard}>
              <Text style={styles.chartTitle}>{series.sensor_name}</Text>
              <MiniChart
                data={series.data.map((d) => d.value)}
                color={colors.emerald[500]}
              />
            </Card>
          ))
        ) : (
          <Text style={styles.noData}>{t("statistics.noData")}</Text>
        )}
      </Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray[100] },
  content: { padding: 16, paddingBottom: 32 },
  periodRow: {
    flexDirection: "row",
    backgroundColor: colors.white,
    borderRadius: 12,
    padding: 4,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: colors.gray[200],
  },
  periodBtn: {
    flex: 1,
    paddingVertical: 10,
    alignItems: "center",
    borderRadius: 10,
  },
  periodBtnActive: {
    backgroundColor: colors.primary[600],
  },
  periodText: {
    fontSize: 14,
    fontWeight: "600",
    color: colors.gray[500],
  },
  periodTextActive: {
    color: colors.white,
  },
  chartCard: { marginBottom: 10 },
  chartTitle: { fontSize: 13, fontWeight: "600", color: colors.gray[700], marginBottom: 8 },
  chartContainer: { overflow: "hidden" },
  chartBars: { flexDirection: "row", alignItems: "flex-end", flex: 1 },
  chartLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 4,
  },
  chartLabel: { fontSize: 10, color: colors.gray[400] },
  noData: { color: colors.gray[400], fontSize: 14, textAlign: "center", paddingVertical: 20 },
});
