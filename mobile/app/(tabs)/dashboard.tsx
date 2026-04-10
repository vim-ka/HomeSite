import { ScrollView, View, Text, StyleSheet, RefreshControl } from "react-native";
import { useTranslation } from "react-i18next";
import { useDashboard } from "../../src/hooks/useDashboard";
import type { ClimateRoom, HeatingCircuit, WaterSupplyItem } from "../../src/hooks/useDashboard";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";
import StatusBadge from "../../src/components/StatusBadge";
import { useTheme } from "../../src/hooks/useTheme";

function fmt(v: number | null): string {
  return v != null ? v.toFixed(1) : "—";
}

function ClimateCard({ room }: { room: ClimateRoom }) {
  const { t } = useTranslation();
  const { colors } = useTheme();
  return (
    <Card style={styles.halfCard}>
      <Text style={[styles.cardTitle, { color: colors.gray[800] }]} numberOfLines={1}>{room.room}</Text>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.temperature")}</Text>
        <Text style={[styles.metricValue, { color: colors.orange[500] }]}>
          {room.temperature != null ? `${fmt(room.temperature)}°` : "—"}
        </Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.humidity")}</Text>
        <Text style={[styles.metricValue, { color: colors.sky[500] }]}>
          {room.humidity != null ? `${fmt(room.humidity)}%` : "—"}
        </Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.pressure")}</Text>
        <Text style={[styles.metricValue, { color: colors.emerald[500] }]}>
          {room.pressure != null ? fmt(room.pressure) : "—"}
        </Text>
      </View>
    </Card>
  );
}

function HeatingCard({ circuit: c }: { circuit: HeatingCircuit }) {
  const { t } = useTranslation();
  const { colors } = useTheme();
  return (
    <Card style={styles.halfCard}>
      <Text style={[styles.cardTitle, { color: colors.gray[800] }]} numberOfLines={1}>{c.circuit}</Text>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.tempSet")}</Text>
        <Text style={[styles.metricValueLg, { color: colors.orange[500] }]}>
          {c.temp_set != null ? `${fmt(c.temp_set)}°` : "—"}
        </Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.tempSupply")}</Text>
        <Text style={[styles.metricValueSm, { color: colors.gray[700] }]}>{c.temp_supply != null ? `${fmt(c.temp_supply)}°` : "—"}</Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.tempReturn")}</Text>
        <Text style={[styles.metricValueSm, { color: colors.gray[700] }]}>{c.temp_return != null ? `${fmt(c.temp_return)}°` : "—"}</Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.pump")}</Text>
        <StatusBadge on={c.pump === "1"} labelOn={t("dashboard.on")} labelOff={t("dashboard.off")} />
      </View>
    </Card>
  );
}

function WaterCard({ item: w }: { item: WaterSupplyItem }) {
  const { t } = useTranslation();
  const { colors } = useTheme();
  return (
    <Card style={styles.halfCard}>
      <Text style={[styles.cardTitle, { color: colors.gray[800] }]} numberOfLines={1}>{w.type}</Text>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.tempSet")}</Text>
        <Text style={[styles.metricValueLg, { color: colors.orange[500] }]}>
          {w.temp_set != null ? `${fmt(w.temp_set)}°` : "—"}
        </Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.temperature")}</Text>
        <Text style={[styles.metricValue, { color: colors.sky[500] }]}>
          {w.temp_fact != null ? `${fmt(w.temp_fact)}°` : "—"}
        </Text>
      </View>
      <View style={styles.metric}>
        <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>{t("dashboard.pump")}</Text>
        <StatusBadge on={w.pump === "1"} labelOn={t("dashboard.on")} labelOff={t("dashboard.off")} />
      </View>
    </Card>
  );
}

export default function DashboardScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const { data, isLoading, error, refetch } = useDashboard();

  if (isLoading) {
    return (
      <View style={styles.center}>
        <Text style={[styles.loadingText, { color: colors.gray[500] }]}>{t("common.loading")}</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={[styles.errorText, { color: colors.red[600] }]}>{t("common.error")}</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={[styles.container, { backgroundColor: colors.gray[100] }]}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={refetch} />}
    >
      <Section title={t("dashboard.climate")}>
        <View style={styles.grid}>
          {data?.climate.map((r) => (
            <ClimateCard key={r.room} room={r} />
          ))}
        </View>
      </Section>

      <Section title={t("dashboard.heating")}>
        <View style={styles.grid}>
          {data?.heating.map((c) => (
            <HeatingCard key={c.circuit} circuit={c} />
          ))}
        </View>
      </Section>

      <Section title={t("dashboard.waterSupply")}>
        {data?.water_supply && data.water_supply.length > 0 ? (
          <View style={styles.grid}>
            {data.water_supply.map((w) => (
              <WaterCard key={w.type} item={w} />
            ))}
          </View>
        ) : (
          <Text style={[styles.noData, { color: colors.gray[400] }]}>{t("dashboard.noData")}</Text>
        )}
      </Section>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: 16, paddingBottom: 32 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  loadingText: { fontSize: 16 },
  errorText: { fontSize: 16 },
  noData: { fontSize: 14 },
  grid: { flexDirection: "row", flexWrap: "wrap", marginHorizontal: -6 },
  halfCard: { width: "47%", marginHorizontal: "1.5%", marginBottom: 12 },
  cardTitle: { fontSize: 14, fontWeight: "700", marginBottom: 10 },
  metric: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 },
  metricLabel: { fontSize: 11, flexShrink: 1 },
  metricValue: { fontSize: 16, fontWeight: "700" },
  metricValueLg: { fontSize: 20, fontWeight: "800" },
  metricValueSm: { fontSize: 14, fontWeight: "600" },
});
