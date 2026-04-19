import { Stack, router } from "expo-router";
import { TouchableOpacity } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTheme } from "../../src/hooks/useTheme";
import { useTranslation } from "react-i18next";

export default function AdminLayout() {
  const { colors, isDark } = useTheme();
  const { t } = useTranslation();
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: isDark ? colors.gray[100] : "#1d4ed8" },
        headerTintColor: isDark ? colors.gray[800] : "#ffffff",
        headerTitleStyle: { fontWeight: "700" },
        contentStyle: { backgroundColor: colors.gray[100] },
        headerLeft: () => (
          <TouchableOpacity
            onPress={() => router.back()}
            style={{ paddingHorizontal: 12, paddingVertical: 6 }}
          >
            <Ionicons
              name="chevron-back"
              size={24}
              color={isDark ? colors.gray[800] : "#ffffff"}
            />
          </TouchableOpacity>
        ),
      }}
    >
      <Stack.Screen name="index" options={{ title: t("admin.title") }} />
      <Stack.Screen name="users" options={{ title: t("admin.users") }} />
      <Stack.Screen name="places" options={{ title: t("admin.places") }} />
      <Stack.Screen name="sensors" options={{ title: t("admin.sensors") }} />
      <Stack.Screen name="sensor-types" options={{ title: t("admin.sensorTypes") }} />
      <Stack.Screen name="mount-points" options={{ title: t("admin.mountPoints") }} />
      <Stack.Screen name="heating-circuits" options={{ title: t("admin.heatingCircuits") }} />
      <Stack.Screen name="actuators" options={{ title: t("admin.actuators") }} />
      <Stack.Screen name="pending" options={{ title: t("admin.pending") }} />
      <Stack.Screen name="devices" options={{ title: t("admin.devices") }} />
      <Stack.Screen name="system" options={{ title: t("admin.system") }} />
      <Stack.Screen name="mqtt" options={{ title: t("admin.mqtt") }} />
      <Stack.Screen name="database" options={{ title: t("admin.database") }} />
      <Stack.Screen name="backups" options={{ title: t("admin.backups") }} />
    </Stack>
  );
}
