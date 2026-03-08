import { Tabs } from "expo-router";
import { useTranslation } from "react-i18next";
import { Platform, Text } from "react-native";
import { colors } from "../../src/theme/colors";

const TAB_ICONS: Record<string, string> = {
  dashboard: "⌂",
  heating: "♨",
  water: "💧",
  stats: "📊",
  more: "⋯",
};

function TabIcon({ name, focused }: { name: string; focused: boolean }) {
  return (
    <Text style={{ fontSize: 22, color: focused ? colors.primary[600] : colors.gray[400] }}>
      {TAB_ICONS[name] ?? "•"}
    </Text>
  );
}

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
          tabBarIcon: ({ focused }) => <TabIcon name="dashboard" focused={focused} />,
          tabBarLabel: t("tabs.dashboard"),
          headerTitle: t("dashboard.title"),
        }}
      />
      <Tabs.Screen
        name="heating"
        options={{
          title: t("tabs.heating"),
          tabBarIcon: ({ focused }) => <TabIcon name="heating" focused={focused} />,
          tabBarLabel: t("tabs.heating"),
          headerTitle: t("heating.title"),
        }}
      />
      <Tabs.Screen
        name="water"
        options={{
          title: t("tabs.water"),
          tabBarIcon: ({ focused }) => <TabIcon name="water" focused={focused} />,
          tabBarLabel: t("tabs.water"),
          headerTitle: t("waterSupply.title"),
        }}
      />
      <Tabs.Screen
        name="stats"
        options={{
          title: t("tabs.stats"),
          tabBarIcon: ({ focused }) => <TabIcon name="stats" focused={focused} />,
          tabBarLabel: t("tabs.stats"),
          headerTitle: t("statistics.title"),
        }}
      />
      <Tabs.Screen
        name="more"
        options={{
          title: t("tabs.settings"),
          tabBarIcon: ({ focused }) => <TabIcon name="more" focused={focused} />,
          tabBarLabel: t("tabs.settings"),
          headerTitle: t("settings.title"),
        }}
      />
    </Tabs>
  );
}
