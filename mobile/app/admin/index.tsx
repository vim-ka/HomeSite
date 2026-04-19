import { ScrollView, View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useTheme } from "../../src/hooks/useTheme";
import Card from "../../src/components/Card";

type IoniconName = React.ComponentProps<typeof Ionicons>["name"];

interface TileDef {
  path: string;
  icon: IoniconName;
  titleKey: string;
  group: "equipment" | "devices" | "system" | "infra";
}

const TILES: TileDef[] = [
  // Equipment
  { path: "/admin/pending", icon: "radio-outline", titleKey: "admin.pending", group: "equipment" },
  { path: "/admin/sensors", icon: "thermometer-outline", titleKey: "admin.sensors", group: "equipment" },
  { path: "/admin/sensor-types", icon: "list-outline", titleKey: "admin.sensorTypes", group: "equipment" },
  { path: "/admin/mount-points", icon: "location-outline", titleKey: "admin.mountPoints", group: "equipment" },
  { path: "/admin/places", icon: "home-outline", titleKey: "admin.places", group: "equipment" },
  { path: "/admin/heating-circuits", icon: "flame-outline", titleKey: "admin.heatingCircuits", group: "equipment" },
  { path: "/admin/actuators", icon: "hardware-chip-outline", titleKey: "admin.actuators", group: "equipment" },
  // Devices
  { path: "/admin/devices", icon: "wifi-outline", titleKey: "admin.devices", group: "devices" },
  // System
  { path: "/admin/system", icon: "options-outline", titleKey: "admin.system", group: "system" },
  // Infra
  { path: "/admin/users", icon: "people-outline", titleKey: "admin.users", group: "infra" },
  { path: "/admin/mqtt", icon: "cloud-outline", titleKey: "admin.mqtt", group: "infra" },
  { path: "/admin/database", icon: "server-outline", titleKey: "admin.database", group: "infra" },
  { path: "/admin/backups", icon: "archive-outline", titleKey: "admin.backups", group: "infra" },
];

const GROUP_ORDER: { id: "equipment" | "devices" | "system" | "infra"; titleKey: string }[] = [
  { id: "equipment", titleKey: "admin.groupEquipment" },
  { id: "devices", titleKey: "admin.groupDevices" },
  { id: "system", titleKey: "admin.groupSystem" },
  { id: "infra", titleKey: "admin.groupInfra" },
];

export default function AdminIndex() {
  const { t } = useTranslation();
  const { colors } = useTheme();

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.gray[100] }}
      contentContainerStyle={styles.content}
    >
      {GROUP_ORDER.map((g) => (
        <View key={g.id} style={{ marginBottom: 18 }}>
          <Text style={[styles.groupTitle, { color: colors.gray[500] }]}>
            {t(g.titleKey).toUpperCase()}
          </Text>
          <Card>
            {TILES.filter((t) => t.group === g.id).map((tile, idx, arr) => (
              <TouchableOpacity
                key={tile.path}
                onPress={() => router.push(tile.path as any)}
                style={[
                  styles.row,
                  idx < arr.length - 1 && { borderBottomWidth: 1, borderBottomColor: colors.gray[100] },
                ]}
              >
                <Ionicons name={tile.icon} size={22} color={colors.primary[600]} style={{ width: 28 }} />
                <Text style={[styles.rowText, { color: colors.gray[800] }]}>
                  {t(tile.titleKey)}
                </Text>
                <Ionicons
                  name="chevron-forward"
                  size={18}
                  color={colors.gray[400]}
                  style={{ marginLeft: "auto" }}
                />
              </TouchableOpacity>
            ))}
          </Card>
        </View>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 40 },
  groupTitle: { fontSize: 11, fontWeight: "700", letterSpacing: 0.5, marginBottom: 6, paddingLeft: 4 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 12,
    gap: 10,
  },
  rowText: { fontSize: 15, fontWeight: "500" },
});
