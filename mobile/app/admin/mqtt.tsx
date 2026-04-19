import { useEffect, useState } from "react";
import { ScrollView, View, Text, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import Card from "../../src/components/Card";
import { TextField } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";

interface MqttSettings {
  host: string;
  port: string;
  user: string;
  password: string;
}

export default function MqttScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const qc = useQueryClient();

  const { data } = useQuery<MqttSettings>({
    queryKey: ["admin-mqtt"],
    queryFn: async () => (await api.get("/settings/mqtt")).data,
  });

  const [form, setForm] = useState<MqttSettings | null>(null);
  useEffect(() => {
    if (data && !form) setForm(data);
  }, [data]);

  const mut = useMutation({
    mutationFn: async (body: MqttSettings) =>
      (await api.put("/settings/mqtt", body)).data,
    onSuccess: (result: any) => {
      qc.invalidateQueries({ queryKey: ["admin-mqtt"] });
      Alert.alert(
        t("admin.saved"),
        result?.gateway_reloaded
          ? t("admin.mqttGatewayReloaded")
          : t("admin.mqttGatewayFailed"),
      );
    },
  });

  if (!form) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.gray[100], padding: 16 }}>
        <Text style={{ color: colors.gray[400] }}>{t("common.loading")}</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.gray[100] }}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
    >
      <Card style={{ marginBottom: 14, padding: 14 }}>
        <View style={{ gap: 12 }}>
          <TextField
            label={t("admin.mqttHost")}
            value={form.host}
            onChangeText={(v) => setForm({ ...form, host: v })}
            autoCapitalize="none"
          />
          <TextField
            label={t("admin.mqttPort")}
            value={form.port}
            onChangeText={(v) => setForm({ ...form, port: v })}
            keyboardType="numeric"
          />
          <TextField
            label={t("admin.mqttUser")}
            value={form.user}
            onChangeText={(v) => setForm({ ...form, user: v })}
            autoCapitalize="none"
          />
          <TextField
            label={t("admin.mqttPass")}
            value={form.password}
            onChangeText={(v) => setForm({ ...form, password: v })}
            secure
            autoCapitalize="none"
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
