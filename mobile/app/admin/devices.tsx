import { View, Text, StyleSheet } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { apiRoot } from "../../src/api/client";
import ListScreen from "../../src/components/ListScreen";
import Card from "../../src/components/Card";
import { useTheme } from "../../src/hooks/useTheme";

interface Device {
  mqtt_device_name: string;
  name: string;
  description: string | null;
  online: boolean;
  last_heartbeat: string | null;
  heartbeat_data: Record<string, any>;
  pending_commands?: number;
  unsynced_commands?: number;
}

interface DevicesResponse {
  devices: Device[];
  online_count: number;
}

function fmtUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}д ${h}ч ${m}м`;
  if (h > 0) return `${h}ч ${m}м`;
  return `${m}м`;
}

export default function DevicesScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();

  const { data, refetch, isFetching } = useQuery<DevicesResponse>({
    queryKey: ["admin-health-devices"],
    queryFn: async () => (await apiRoot.get("/health/devices")).data,
    refetchInterval: 15_000,
  });

  return (
    <ListScreen
      refreshing={isFetching}
      onRefresh={refetch}
      empty={!data || data.devices.length === 0}
    >
      {data?.devices.map((d) => {
        const uptime = d.heartbeat_data?.uptime;
        const heap = d.heartbeat_data?.heap;
        return (
          <Card key={d.mqtt_device_name} style={{ marginBottom: 10 }}>
            <View style={styles.header}>
              <Text style={[styles.title, { color: colors.gray[800] }]}>
                {d.name} <Text style={{ color: colors.gray[400], fontSize: 12 }}>({d.mqtt_device_name})</Text>
              </Text>
              <View
                style={[
                  styles.badge,
                  { backgroundColor: d.online ? colors.green[500] : colors.red[500] },
                ]}
              >
                <Text style={styles.badgeText}>
                  {d.online ? t("admin.deviceOnline") : t("admin.deviceOffline")}
                </Text>
              </View>
            </View>
            {d.description && (
              <Text style={[styles.desc, { color: colors.gray[500] }]}>{d.description}</Text>
            )}
            <View style={styles.grid}>
              {uptime != null && (
                <View style={styles.metric}>
                  <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>
                    {t("admin.deviceUptime")}
                  </Text>
                  <Text style={[styles.metricValue, { color: colors.gray[800] }]}>
                    {fmtUptime(Number(uptime))}
                  </Text>
                </View>
              )}
              {heap != null && (
                <View style={styles.metric}>
                  <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>
                    {t("admin.deviceHeap")}
                  </Text>
                  <Text style={[styles.metricValue, { color: colors.gray[800] }]}>
                    {(Number(heap) / 1024).toFixed(1)} KB
                  </Text>
                </View>
              )}
              {d.last_heartbeat && (
                <View style={styles.metric}>
                  <Text style={[styles.metricLabel, { color: colors.gray[500] }]}>
                    {t("admin.deviceLastSeen")}
                  </Text>
                  <Text style={[styles.metricValue, { color: colors.gray[800] }]}>
                    {new Date(d.last_heartbeat).toLocaleString("ru-RU")}
                  </Text>
                </View>
              )}
            </View>
          </Card>
        );
      })}
    </ListScreen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 4 },
  title: { fontSize: 15, fontWeight: "700", flex: 1 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 10 },
  badgeText: { color: "#ffffff", fontSize: 11, fontWeight: "700" },
  desc: { fontSize: 12, marginBottom: 6 },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: 12, marginTop: 4 },
  metric: { minWidth: "30%" },
  metricLabel: { fontSize: 10 },
  metricValue: { fontSize: 13, fontWeight: "600" },
});
