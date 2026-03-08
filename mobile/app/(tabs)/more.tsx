import { useState } from "react";
import {
  ScrollView,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  Alert,
  FlatList,
} from "react-native";
import { router } from "expo-router";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import { useAuthStore } from "../../src/stores/authStore";
import { setBaseURL } from "../../src/api/client";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";
import { colors } from "../../src/theme/colors";

interface EventItem {
  id: number;
  timestamp: string;
  level: string;
  source: string;
  message: string;
}

interface PaginatedEvents {
  items: EventItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export default function MoreScreen() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { username, role, serverUrl, setServerUrl, logout } = useAuthStore();

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

  // Events
  const [eventsPage, setEventsPage] = useState(1);
  const { data: events } = useQuery<PaginatedEvents>({
    queryKey: ["events", eventsPage],
    queryFn: async () => {
      const { data } = await api.get(`/events?page=${eventsPage}&page_size=20`);
      return data;
    },
  });

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* User info */}
      <Card style={styles.userCard}>
        <View style={styles.userRow}>
          <View style={styles.avatar}>
            <Text style={styles.avatarText}>{(username ?? "U")[0].toUpperCase()}</Text>
          </View>
          <View style={styles.userInfo}>
            <Text style={styles.userName}>{username}</Text>
            <Text style={styles.userRole}>{role}</Text>
          </View>
        </View>
      </Card>

      {/* Server URL */}
      <Section title={t("settings.serverUrl")}>
        <Card>
          <TextInput
            style={styles.input}
            value={urlInput}
            onChangeText={setUrlInput}
            placeholder="http://192.168.1.100:8000"
            autoCapitalize="none"
            keyboardType="url"
          />
          <TouchableOpacity style={styles.saveBtn} onPress={handleSaveUrl}>
            <Text style={styles.saveBtnText}>
              {urlSaved ? "OK" : t("common.save")}
            </Text>
          </TouchableOpacity>
        </Card>
      </Section>

      {/* Events */}
      <Section title={t("events.title")}>
        <Card>
          {events && events.items.length > 0 ? (
            <>
              {events.items.map((ev) => (
                <View key={ev.id} style={styles.eventRow}>
                  <View style={styles.eventHeader}>
                    <View style={[
                      styles.levelBadge,
                      ev.level === "error" && styles.levelError,
                      ev.level === "warning" && styles.levelWarn,
                    ]}>
                      <Text style={styles.levelText}>{ev.level}</Text>
                    </View>
                    <Text style={styles.eventTime}>
                      {new Date(ev.timestamp).toLocaleString("ru-RU")}
                    </Text>
                  </View>
                  <Text style={styles.eventMsg}>{ev.message}</Text>
                </View>
              ))}
              {events.total_pages > 1 && (
                <View style={styles.pagination}>
                  <TouchableOpacity
                    disabled={eventsPage <= 1}
                    onPress={() => setEventsPage((p) => p - 1)}
                    style={[styles.pageBtn, eventsPage <= 1 && styles.pageBtnDisabled]}
                  >
                    <Text style={styles.pageBtnText}>{"<"}</Text>
                  </TouchableOpacity>
                  <Text style={styles.pageInfo}>{eventsPage} / {events.total_pages}</Text>
                  <TouchableOpacity
                    disabled={eventsPage >= events.total_pages}
                    onPress={() => setEventsPage((p) => p + 1)}
                    style={[styles.pageBtn, eventsPage >= events.total_pages && styles.pageBtnDisabled]}
                  >
                    <Text style={styles.pageBtnText}>{">"}</Text>
                  </TouchableOpacity>
                </View>
              )}
            </>
          ) : (
            <Text style={styles.noData}>{t("events.noEvents")}</Text>
          )}
        </Card>
      </Section>

      {/* About */}
      <Section title={t("settings.about")}>
        <Card>
          <Text style={styles.aboutText}>HomeSite — {t("settings.version")} 2.0</Text>
          <Text style={styles.aboutSub}>React Native + Expo</Text>
        </Card>
      </Section>

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>{t("settings.logout")}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray[100] },
  content: { padding: 16, paddingBottom: 40 },
  userCard: { marginBottom: 20 },
  userRow: { flexDirection: "row", alignItems: "center" },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.primary[600],
    justifyContent: "center",
    alignItems: "center",
  },
  avatarText: { color: colors.white, fontSize: 20, fontWeight: "700" },
  userInfo: { marginLeft: 14 },
  userName: { fontSize: 17, fontWeight: "700", color: colors.gray[800] },
  userRole: { fontSize: 13, color: colors.gray[500], marginTop: 2 },
  input: {
    borderWidth: 1,
    borderColor: colors.gray[200],
    borderRadius: 10,
    padding: 12,
    fontSize: 15,
    backgroundColor: colors.gray[50],
  },
  saveBtn: {
    marginTop: 10,
    backgroundColor: colors.primary[600],
    borderRadius: 10,
    padding: 12,
    alignItems: "center",
  },
  saveBtnText: { color: colors.white, fontWeight: "600", fontSize: 15 },
  eventRow: {
    borderBottomWidth: 1,
    borderBottomColor: colors.gray[100],
    paddingVertical: 10,
  },
  eventHeader: { flexDirection: "row", alignItems: "center", marginBottom: 4 },
  levelBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
    backgroundColor: colors.gray[100],
    marginRight: 8,
  },
  levelError: { backgroundColor: colors.red[100] },
  levelWarn: { backgroundColor: colors.amber[100] },
  levelText: { fontSize: 11, fontWeight: "600", color: colors.gray[600] },
  eventTime: { fontSize: 11, color: colors.gray[400] },
  eventMsg: { fontSize: 13, color: colors.gray[700] },
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
    backgroundColor: colors.primary[600],
    justifyContent: "center",
    alignItems: "center",
  },
  pageBtnDisabled: { backgroundColor: colors.gray[200] },
  pageBtnText: { color: colors.white, fontWeight: "700", fontSize: 16 },
  pageInfo: { fontSize: 14, color: colors.gray[600] },
  noData: { color: colors.gray[400], fontSize: 14, textAlign: "center", paddingVertical: 16 },
  aboutText: { fontSize: 15, color: colors.gray[700], fontWeight: "600" },
  aboutSub: { fontSize: 13, color: colors.gray[400], marginTop: 4 },
  logoutBtn: {
    backgroundColor: colors.red[500],
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  logoutText: { color: colors.white, fontWeight: "700", fontSize: 16 },
});
