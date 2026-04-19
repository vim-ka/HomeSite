import { useState } from "react";
import {
  ScrollView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
} from "react-native";
import { router } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import { useAuthStore } from "../../src/stores/authStore";
import { useThemeStore, type ThemeMode } from "../../src/stores/themeStore";
import { useLangStore, type Language } from "../../src/stores/langStore";
import { setBaseURL } from "../../src/api/client";
import { useTheme } from "../../src/hooks/useTheme";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";

interface EventItem {
  id: number;
  timestamp: string;
  level: string;
  source: string;
  message: string;
  username: string | null;
}

interface PaginatedEvents {
  items: EventItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const THEME_OPTIONS: { key: ThemeMode; label: string }[] = [
  { key: "light", label: "☀️" },
  { key: "dark", label: "🌙" },
  { key: "system", label: "⚙️" },
];

const LANG_OPTIONS: { key: Language; label: string }[] = [
  { key: "ru", label: "RU" },
  { key: "en", label: "EN" },
];

export default function MoreScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const queryClient = useQueryClient();
  const { username, role, serverUrl, setServerUrl, logout } = useAuthStore();
  const { theme, setTheme } = useThemeStore();
  const { lang, setLang } = useLangStore();

  const [urlInput, setUrlInput] = useState(serverUrl);
  const [urlSaved, setUrlSaved] = useState(false);

  const handleSaveUrl = () => {
    setServerUrl(urlInput);
    setBaseURL(urlInput);
    queryClient.invalidateQueries();
    setUrlSaved(true);
    setTimeout(() => setUrlSaved(false), 2000);
  };

  const handleLogout = () => {
    Alert.alert(t("settings.logout"), "", [
      { text: t("common.cancel"), style: "cancel" },
      {
        text: t("settings.logout"),
        style: "destructive",
        onPress: () => {
          logout();
          router.replace("/login");
        },
      },
    ]);
  };

  const [eventsPage, setEventsPage] = useState(1);
  const [levelFilter, setLevelFilter] = useState<"" | "INFO" | "WARNING" | "ERROR">("");
  const { data: events } = useQuery<PaginatedEvents>({
    queryKey: ["events", eventsPage, levelFilter],
    queryFn: async () => {
      const params = new URLSearchParams({ page: String(eventsPage), per_page: "20" });
      if (levelFilter) params.set("level", levelFilter);
      const { data } = await api.get(`/events?${params}`);
      return data;
    },
  });

  const LEVEL_FILTERS: { key: "" | "INFO" | "WARNING" | "ERROR"; label: string }[] = [
    { key: "", label: t("events.filterAll") },
    { key: "INFO", label: "INFO" },
    { key: "WARNING", label: "WARN" },
    { key: "ERROR", label: "ERR" },
  ];

  return (
    <ScrollView style={[styles.container, { backgroundColor: colors.gray[100] }]} contentContainerStyle={styles.content}>
      {/* User info */}
      <Card style={styles.userCard}>
        <View style={styles.userRow}>
          <View style={[styles.avatar, { backgroundColor: colors.primary[600] }]}>
            <Text style={styles.avatarText}>{(username ?? "U")[0].toUpperCase()}</Text>
          </View>
          <View style={styles.userInfo}>
            <Text style={[styles.userName, { color: colors.gray[800] }]}>{username}</Text>
            <Text style={[styles.userRole, { color: colors.gray[500] }]}>{role}</Text>
          </View>
        </View>
      </Card>

      {/* Admin section */}
      {role === "admin" && (
        <Section title={t("settings.adminSettings")}>
          <Card>
            <TouchableOpacity
              style={[styles.adminLink, { borderBottomColor: colors.gray[100] }]}
              onPress={() => router.push("/admin")}
            >
              <Ionicons name="construct-outline" size={20} color={colors.primary[600]} />
              <Text style={[styles.adminLinkText, { color: colors.gray[800] }]}>
                {t("settings.adminPanel")}
              </Text>
              <Ionicons name="chevron-forward" size={18} color={colors.gray[400]} style={{ marginLeft: "auto" }} />
            </TouchableOpacity>
          </Card>
        </Section>
      )}

      {/* Theme selector */}
      <Section title={t("settings.theme")}>
        <Card>
          <View style={styles.themeRow}>
            {THEME_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.key}
                style={[
                  styles.themeBtn,
                  { borderColor: colors.gray[200], backgroundColor: colors.gray[100] },
                  theme === opt.key && { backgroundColor: colors.primary[600], borderColor: colors.primary[600] },
                ]}
                onPress={() => setTheme(opt.key)}
              >
                <Text style={styles.themeEmoji}>{opt.label}</Text>
                <Text style={[
                  styles.themeLabel,
                  { color: colors.gray[600] },
                  theme === opt.key && { color: "#ffffff", fontWeight: "700" },
                ]}>
                  {t(`settings.theme_${opt.key}`)}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </Card>
      </Section>

      {/* Language selector */}
      <Section title={t("settings.language")}>
        <Card>
          <View style={styles.themeRow}>
            {LANG_OPTIONS.map((opt) => (
              <TouchableOpacity
                key={opt.key}
                style={[
                  styles.themeBtn,
                  { borderColor: colors.gray[200], backgroundColor: colors.gray[100] },
                  lang === opt.key && { backgroundColor: colors.primary[600], borderColor: colors.primary[600] },
                ]}
                onPress={() => setLang(opt.key)}
              >
                <Text style={[
                  styles.themeLabel,
                  { color: colors.gray[600], fontSize: 14, fontWeight: "700" },
                  lang === opt.key && { color: "#ffffff" },
                ]}>
                  {opt.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </Card>
      </Section>

      {/* Server URL */}
      <Section title={t("settings.serverUrl")}>
        <Card>
          <TextInput
            style={[styles.input, { borderColor: colors.gray[200], backgroundColor: colors.gray[50], color: colors.gray[800] }]}
            value={urlInput}
            onChangeText={setUrlInput}
            placeholder="http://192.168.1.100:8000"
            placeholderTextColor={colors.gray[400]}
            autoCapitalize="none"
            keyboardType="url"
          />
          <TouchableOpacity style={[styles.saveBtn, { backgroundColor: colors.primary[600] }]} onPress={handleSaveUrl}>
            <Text style={styles.saveBtnText}>
              {urlSaved ? "OK" : t("common.save")}
            </Text>
          </TouchableOpacity>
        </Card>
      </Section>

      {/* Events */}
      <Section title={t("events.title")}>
        <Card>
          <View style={styles.levelFilterRow}>
            {LEVEL_FILTERS.map((lf) => (
              <TouchableOpacity
                key={lf.key || "all"}
                onPress={() => { setLevelFilter(lf.key); setEventsPage(1); }}
                style={[
                  styles.levelFilterBtn,
                  { backgroundColor: colors.gray[100], borderColor: colors.gray[200] },
                  levelFilter === lf.key && { backgroundColor: colors.primary[600], borderColor: colors.primary[600] },
                ]}
              >
                <Text style={[
                  styles.levelFilterText,
                  { color: colors.gray[600] },
                  levelFilter === lf.key && { color: "#ffffff", fontWeight: "700" },
                ]}>
                  {lf.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          {events && events.items.length > 0 ? (
            <>
              {events.items.map((ev) => (
                <View key={ev.id} style={[styles.eventRow, { borderBottomColor: colors.gray[100] }]}>
                  <View style={styles.eventHeader}>
                    <View style={[
                      styles.levelBadge,
                      { backgroundColor: colors.gray[100] },
                      ev.level === "ERROR" && { backgroundColor: colors.red[100] },
                      ev.level === "WARNING" && { backgroundColor: colors.amber[100] },
                    ]}>
                      <Text style={[styles.levelText, { color: colors.gray[600] }]}>{ev.level}</Text>
                    </View>
                    <Text style={[styles.eventUser, { color: colors.gray[500] }]}>{ev.username ?? "—"}</Text>
                    <Text style={[styles.eventTime, { color: colors.gray[400] }]}>
                      {new Date(ev.timestamp).toLocaleString("ru-RU")}
                    </Text>
                  </View>
                  <Text style={[styles.eventMsg, { color: colors.gray[700] }]}>{ev.message}</Text>
                </View>
              ))}
              {events.total_pages > 1 && (
                <View style={styles.pagination}>
                  <TouchableOpacity
                    disabled={eventsPage <= 1}
                    onPress={() => setEventsPage((p) => p - 1)}
                    style={[styles.pageBtn, { backgroundColor: colors.primary[600] }, eventsPage <= 1 && { backgroundColor: colors.gray[200] }]}
                  >
                    <Text style={styles.pageBtnText}>{"<"}</Text>
                  </TouchableOpacity>
                  <Text style={[styles.pageInfo, { color: colors.gray[600] }]}>{eventsPage} / {events.total_pages}</Text>
                  <TouchableOpacity
                    disabled={eventsPage >= events.total_pages}
                    onPress={() => setEventsPage((p) => p + 1)}
                    style={[styles.pageBtn, { backgroundColor: colors.primary[600] }, eventsPage >= events.total_pages && { backgroundColor: colors.gray[200] }]}
                  >
                    <Text style={styles.pageBtnText}>{">"}</Text>
                  </TouchableOpacity>
                </View>
              )}
            </>
          ) : (
            <Text style={[styles.noData, { color: colors.gray[400] }]}>{t("events.noEvents")}</Text>
          )}
        </Card>
      </Section>

      {/* About */}
      <Section title={t("settings.about")}>
        <Card>
          <Text style={[styles.aboutText, { color: colors.gray[700] }]}>HomeSite — {t("settings.version")} 2.0</Text>
          <Text style={[styles.aboutSub, { color: colors.gray[400] }]}>React Native + Expo</Text>
        </Card>
      </Section>

      {/* Logout */}
      <TouchableOpacity style={[styles.logoutBtn, { backgroundColor: colors.red[500] }]} onPress={handleLogout}>
        <Text style={styles.logoutText}>{t("settings.logout")}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  content: { padding: 16, paddingBottom: 40 },
  userCard: { marginBottom: 20 },
  userRow: { flexDirection: "row", alignItems: "center" },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
  },
  avatarText: { color: "#ffffff", fontSize: 20, fontWeight: "700" },
  userInfo: { marginLeft: 14 },
  userName: { fontSize: 17, fontWeight: "700" },
  userRole: { fontSize: 13, marginTop: 2 },
  themeRow: { flexDirection: "row", gap: 8 },
  themeBtn: {
    flex: 1,
    alignItems: "center",
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
  },
  themeEmoji: { fontSize: 20, marginBottom: 4 },
  themeLabel: { fontSize: 12 },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
  },
  saveBtn: {
    marginTop: 10,
    borderRadius: 10,
    padding: 12,
    alignItems: "center",
  },
  saveBtnText: { color: "#ffffff", fontWeight: "600", fontSize: 15 },
  eventRow: {
    borderBottomWidth: 1,
    paddingVertical: 10,
  },
  eventHeader: { flexDirection: "row", alignItems: "center", marginBottom: 4, gap: 6 },
  levelBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  levelText: { fontSize: 11, fontWeight: "600" },
  eventUser: { fontSize: 11, fontWeight: "500" },
  eventTime: { fontSize: 11, marginLeft: "auto" },
  eventMsg: { fontSize: 13 },
  pagination: {
    flexDirection: "row",
    justifyContent: "center",
    alignItems: "center",
    marginTop: 12,
    gap: 16,
  },
  pageBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: "center",
    alignItems: "center",
  },
  pageBtnText: { color: "#ffffff", fontWeight: "700", fontSize: 16 },
  pageInfo: { fontSize: 14 },
  noData: { fontSize: 14, textAlign: "center", paddingVertical: 16 },
  levelFilterRow: { flexDirection: "row", gap: 6, marginBottom: 10 },
  levelFilterBtn: {
    flex: 1,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: "center",
  },
  levelFilterText: { fontSize: 11, fontWeight: "600" },
  adminLink: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingVertical: 8,
  },
  adminLinkText: { fontSize: 15, fontWeight: "600" },
  aboutText: { fontSize: 15, fontWeight: "600" },
  aboutSub: { fontSize: 13, marginTop: 4 },
  logoutBtn: {
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  logoutText: { color: "#ffffff", fontWeight: "700", fontSize: 16 },
});
