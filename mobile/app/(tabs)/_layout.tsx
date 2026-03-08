import { Tabs } from "expo-router";
import { useTranslation } from "react-i18next";
import { Platform } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors } from "../../src/theme/colors";

type IconName = React.ComponentProps<typeof Ionicons>["name"];

const TAB_ICONS: Record<string, { focused: IconName; default: IconName }> = {
  dashboard: { focused: "home", default: "home-outline" },
  heating: { focused: "flame", default: "flame-outline" },
  water: { focused: "water", default: "water-outline" },
  stats: { focused: "bar-chart", default: "bar-chart-outline" },
  more: { focused: "ellipsis-horizontal", default: "ellipsis-horizontal-outline" },
};

export default function TabLayout() {
  const { t } = useTranslation();

  return (
    <Tabs
      screenOptions={{
        headerStyle: {
          backgroundColor: colors.primary[700],
        },
        headerTintColor: colors.white,
        headerTitleStyle: { fontWeight: "700" },
        tabBarActiveTintColor: colors.primary[600],
        tabBarInactiveTintColor: colors.gray[400],
        tabBarStyle: {
          backgroundColor: colors.white,
          borderTopColor: colors.gray[200],
          height: Platform.OS === "ios" ? 85 : 60,
          paddingBottom: Platform.OS === "ios" ? 25 : 8,
          paddingTop: 8,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: "600",
        },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: t("tabs.dashboard"),
          tabBarIcon: ({ focused, color, size }) => (
            <Ionicons name={TAB_ICONS.dashboard[focused ? "focused" : "default"]} size={size} color={color} />
          ),
          tabBarLabel: t("tabs.dashboard"),
          headerTitle: t("dashboard.title"),
        }}
      />
      <Tabs.Screen
        name="heating"
        options={{
          title: t("tabs.heating"),
          tabBarIcon: ({ focused, color, size }) => (
            <Ionicons name={TAB_ICONS.heating[focused ? "focused" : "default"]} size={size} color={color} />
          ),
          tabBarLabel: t("tabs.heating"),
          headerTitle: t("heating.title"),
        }}
      />
      <Tabs.Screen
        name="water"
        options={{
          title: t("tabs.water"),
          tabBarIcon: ({ focused, color, size }) => (
            <Ionicons name={TAB_ICONS.water[focused ? "focused" : "default"]} size={size} color={color} />
          ),
          tabBarLabel: t("tabs.water"),
          headerTitle: t("waterSupply.title"),
        }}
      />
      <Tabs.Screen
        name="stats"
        options={{
          title: t("tabs.stats"),
          tabBarIcon: ({ focused, color, size }) => (
            <Ionicons name={TAB_ICONS.stats[focused ? "focused" : "default"]} size={size} color={color} />
          ),
          tabBarLabel: t("tabs.stats"),
          headerTitle: t("statistics.title"),
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: t("tabs.settings"),
          tabBarIcon: ({ focused, color, size }) => (
            <Ionicons name={TAB_ICONS.more[focused ? "focused" : "default"]} size={size} color={color} />
          ),
          tabBarLabel: t("tabs.settings"),
          headerTitle: t("settings.title"),
        }}
      />
    </Tabs>
  );
}
