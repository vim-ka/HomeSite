import { useEffect, useState } from "react";
import { ScrollView, View, Text, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "../../src/api/client";
import Card from "../../src/components/Card";
import { TextField, PickerField } from "../../src/components/Field";
import { useTheme } from "../../src/hooks/useTheme";

interface DbInfo {
  type: "sqlite" | "postgresql";
  url: string;
}

export default function DatabaseScreen() {
  const { t } = useTranslation();
  const { colors } = useTheme();
  const qc = useQueryClient();

  const { data } = useQuery<DbInfo>({
    queryKey: ["admin-db-info"],
    queryFn: async () => (await api.get("/settings/database")).data,
  });

  const [type, setType] = useState<"sqlite" | "postgresql">("sqlite");
  const [sqlitePath, setSqlitePath] = useState("./sensors.db");
  const [pg, setPg] = useState({ host: "", port: "5432", dbname: "", user: "", password: "" });

  useEffect(() => {
    if (!data) return;
    setType(data.type);
    if (data.type === "sqlite") {
      const m = data.url.match(/sqlite.*:\/\/\/(.+)/);
      if (m?.[1]) setSqlitePath(m[1]);
    }
  }, [data]);

  const mut = useMutation({
    mutationFn: async () =>
      api.put("/settings/database", {
        type,
        ...(type === "sqlite"
          ? { path: sqlitePath }
          : {
              host: pg.host,
              port: parseInt(pg.port, 10),
              dbname: pg.dbname,
              user: pg.user,
              password: pg.password,
            }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-db-info"] });
      Alert.alert(t("admin.saved"), t("admin.restartRequired"));
    },
    onError: (err: any) => {
      Alert.alert(t("common.error"), err?.response?.data?.detail ?? String(err));
    },
  });

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.gray[100] }}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
    >
      <Card style={{ marginBottom: 14, padding: 14 }}>
        <View style={{ gap: 12 }}>
          <PickerField
            label={t("admin.dbType")}
            value={type}
            options={[
              { value: "sqlite", label: "SQLite" },
              { value: "postgresql", label: "PostgreSQL" },
            ]}
            onChange={(v) => setType(v as any)}
          />
          {type === "sqlite" ? (
            <TextField
              label={t("admin.dbPath")}
              value={sqlitePath}
              onChangeText={setSqlitePath}
              autoCapitalize="none"
            />
          ) : (
            <>
              <TextField
                label={t("admin.dbHost")}
                value={pg.host}
                onChangeText={(v) => setPg({ ...pg, host: v })}
                autoCapitalize="none"
              />
              <TextField
                label={t("admin.dbPort")}
                value={pg.port}
                onChangeText={(v) => setPg({ ...pg, port: v })}
                keyboardType="numeric"
              />
              <TextField
                label={t("admin.dbName")}
                value={pg.dbname}
                onChangeText={(v) => setPg({ ...pg, dbname: v })}
                autoCapitalize="none"
              />
              <TextField
                label={t("admin.dbUser")}
                value={pg.user}
                onChangeText={(v) => setPg({ ...pg, user: v })}
                autoCapitalize="none"
              />
              <TextField
                label={t("admin.dbPassword")}
                value={pg.password}
                onChangeText={(v) => setPg({ ...pg, password: v })}
                secure
                autoCapitalize="none"
              />
            </>
          )}
        </View>
      </Card>

      <TouchableOpacity
        onPress={() => mut.mutate()}
        style={[styles.saveBtn, { backgroundColor: colors.primary[600] }]}
      >
        <Text style={styles.saveBtnText}>{t("admin.save")}</Text>
      </TouchableOpacity>

      <Text style={[styles.warning, { color: colors.amber[600] }]}>
        {t("admin.restartRequired")}
      </Text>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  saveBtn: { padding: 14, borderRadius: 10, alignItems: "center" },
  saveBtnText: { color: "#ffffff", fontSize: 15, fontWeight: "700" },
  warning: { fontSize: 12, marginTop: 10, textAlign: "center" },
});
