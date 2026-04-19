import { useEffect, useMemo, useState } from "react";
import { ScrollView, View, Text, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import Card from "../../src/components/Card";
import { TextField, PickerField } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";

interface KV {
  key: string;
  value: string;
}

const SYSTEM_KEYS: { key: string; i18nKey: string; keyboard?: "numeric" | "default" }[] = [
  { key: "access_token_expire_minutes", i18nKey: "admin.tokenExpireMinutes", keyboard: "numeric" },
  { key: "refresh_token_expire_days", i18nKey: "admin.refreshExpireDays", keyboard: "numeric" },
  { key: "sensor_stale_minutes", i18nKey: "admin.sensorStaleMinutes", keyboard: "numeric" },
  { key: "health_poll_seconds", i18nKey: "admin.healthPollSeconds", keyboard: "numeric" },
  { key: "chart_history_days", i18nKey: "admin.chartHistoryDays", keyboard: "numeric" },
  { key: "ack_timeout_seconds", i18nKey: "admin.ackTimeout", keyboard: "numeric" },
  { key: "heartbeat_timeout_seconds", i18nKey: "admin.heartbeatTimeout", keyboard: "numeric" },
  { key: "gateway_timeout_seconds", i18nKey: "admin.gatewayTimeout", keyboard: "numeric" },
  { key: "frontend_poll_seconds", i18nKey: "admin.frontendPollSeconds", keyboard: "numeric" },
  { key: "mqtt_topic_prefix", i18nKey: "admin.mqttTopicPrefix" },
  { key: "device_gateway_url", i18nKey: "admin.gatewayUrl" },
];

const LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"];
const DEFAULTS: Record<string, string> = {
  access_token_expire_minutes: "30",
  refresh_token_expire_days: "7",
  sensor_stale_minutes: "5",
  health_poll_seconds: "30",
  gateway_timeout_seconds: "5",
  ack_timeout_seconds: "30",
  heartbeat_timeout_seconds: "60",
  chart_history_days: "100",
  frontend_poll_seconds: "30",
  mqtt_topic_prefix: "home/devices/",
  log_level: "INFO",
  device_gateway_url: "http://localhost:8001",
};

export default function SystemScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const qc = useQueryClient();

  const { data } = useQuery<KV[]>({
    queryKey: ["admin-all-settings"],
    queryFn: async () => (await api.get("/settings")).data,
  });

  const kvMap = useMemo(
    () => Object.fromEntries((data ?? []).map((s) => [s.key, s.value])),
    [data],
  );

  const [form, setForm] = useState<Record<string, string> | null>(null);
  useEffect(() => {
    if (data && !form) {
      const init: Record<string, string> = {};
      for (const k of SYSTEM_KEYS) init[k.key] = kvMap[k.key] ?? DEFAULTS[k.key] ?? "";
      init.log_level = kvMap.log_level ?? DEFAULTS.log_level;
      setForm(init);
    }
  }, [data]);

  const mut = useMutation({
    mutationFn: async (body: Record<string, string>) =>
      api.put("/settings", { settings: body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-all-settings"] });
      Alert.alert(t("admin.saved"));
    },
  });

  if (!form) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.gray[100], padding: 16 }}>
        <Text style={{ color: colors.gray[400] }}>{t("common.loading")}</Text>
      </View>
    );
  }

  const set = (k: string, v: string) => setForm((f) => ({ ...(f as any), [k]: v }));

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.gray[100] }}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
    >
      <Card style={{ marginBottom: 14, padding: 14 }}>
        <View style={{ gap: 12 }}>
          {SYSTEM_KEYS.map((f) => (
            <TextField
              key={f.key}
              label={t(f.i18nKey)}
              value={form[f.key] ?? ""}
              onChangeText={(v) => set(f.key, v)}
              keyboardType={f.keyboard}
              autoCapitalize="none"
            />
          ))}
          <PickerField
            label={t("admin.logLevel")}
            value={form.log_level}
            options={LOG_LEVELS.map((l) => ({ value: l, label: l }))}
            onChange={(v) => set("log_level", v)}
          />
        </View>
      </Card>

      <TouchableOpacity
        onPress={() => mut.mutate(form)}
        style={[styles.saveBtn, { backgroundColor: colors.primary[600] }]}
      >
        <Text style={styles.saveBtnText}>{t("admin.save")}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  saveBtn: { padding: 14, borderRadius: 10, alignItems: "center" },
  saveBtnText: { color: "#ffffff", fontSize: 15, fontWeight: "700" },
});
