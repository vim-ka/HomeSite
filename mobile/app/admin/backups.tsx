import { useEffect, useState } from "react";
import { ScrollView, View, Text, TouchableOpacity, StyleSheet, Switch, Alert } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import Card from "../../src/components/Card";
import Row from "../../src/components/Row";
import { TextField, PickerField, Field } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";
import { Ionicons } from "@expo/vector-icons";

interface BackupInfo {
  filename: string;
  size_bytes: number;
  created_at: string;
}

interface BackupSchedule {
  enabled: boolean;
  interval: "daily" | "weekly";
  time: string;
}

function fmtBytes(b: number): string {
  if (b >= 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024).toFixed(1)} KB`;
}

export default function BackupsScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const qc = useQueryClient();

  const { data: backups, refetch, isFetching } = useQuery<BackupInfo[]>({
    queryKey: ["admin-backups"],
    queryFn: async () => (await api.get("/settings/backups")).data,
  });

  const { data: schedule } = useQuery<BackupSchedule>({
    queryKey: ["admin-backup-schedule"],
    queryFn: async () => (await api.get("/settings/backup-schedule")).data,
  });

  const [sForm, setSForm] = useState<BackupSchedule | null>(null);
  useEffect(() => {
    if (schedule && !sForm) setSForm(schedule);
  }, [schedule]);

  const createMut = useMutation({
    mutationFn: async () => api.post("/settings/backup"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-backups"] });
      Alert.alert(t("admin.saved"));
    },
  });

  const saveScheduleMut = useMutation({
    mutationFn: async (body: BackupSchedule) =>
      api.put("/settings/backup-schedule", body),
    onSuccess: () => Alert.alert(t("admin.saved")),
  });

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.gray[100] }}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
    >
      {/* Create backup */}
      <TouchableOpacity
        onPress={() => createMut.mutate()}
        style={[styles.primaryBtn, { backgroundColor: colors.primary[600] }]}
      >
        <Ionicons name="archive-outline" size={18} color="#ffffff" />
        <Text style={styles.primaryBtnText}>{t("admin.createBackup")}</Text>
      </TouchableOpacity>

      {/* Schedule */}
      {sForm && (
        <Card style={{ padding: 14, marginBottom: 16 }}>
          <Text style={[styles.title, { color: colors.gray[700] }]}>
            {t("admin.scheduleEnabled")}
          </Text>
          <View style={{ gap: 12, marginTop: 10 }}>
            <Field label={t("admin.scheduleEnabled")}>
              <Switch
                value={sForm.enabled}
                onValueChange={(v) => setSForm({ ...sForm, enabled: v })}
                trackColor={{ false: colors.gray[300], true: colors.primary[600] }}
              />
            </Field>
            <PickerField
              label={t("admin.scheduleInterval")}
              value={sForm.interval}
              options={[
                { value: "daily", label: t("admin.daily") },
                { value: "weekly", label: t("admin.weekly") },
              ]}
              onChange={(v) => setSForm({ ...sForm, interval: v as "daily" | "weekly" })}
            />
            <TextField
              label={t("admin.scheduleTime")}
              value={sForm.time}
              onChangeText={(v) => setSForm({ ...sForm, time: v })}
              placeholder="03:00"
            />
            <TouchableOpacity
              onPress={() => saveScheduleMut.mutate(sForm)}
              style={[styles.saveSmall, { backgroundColor: colors.primary[600] }]}
            >
              <Text style={{ color: "#ffffff", fontWeight: "700" }}>{t("admin.save")}</Text>
            </TouchableOpacity>
          </View>
        </Card>
      )}

      {/* List */}
      <Text style={[styles.title, { color: colors.gray[700], marginBottom: 8 }]}>
        {t("admin.backups")} ({backups?.length ?? 0})
      </Text>
      {backups && backups.length > 0 ? (
        backups.map((b) => (
          <Row
            key={b.filename}
            title={b.filename}
            subtitle={`${fmtBytes(b.size_bytes)} · ${new Date(b.created_at).toLocaleString("ru-RU")}`}
          />
        ))
      ) : (
        <Card>
          <Text style={{ color: colors.gray[400], textAlign: "center", paddingVertical: 16 }}>
            {t("admin.noBackups")}
          </Text>
        </Card>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  primaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    padding: 14,
    borderRadius: 10,
    marginBottom: 16,
  },
  primaryBtnText: { color: "#ffffff", fontSize: 15, fontWeight: "700" },
  title: { fontSize: 13, fontWeight: "700" },
  saveSmall: { padding: 10, borderRadius: 8, alignItems: "center", marginTop: 4 },
});
