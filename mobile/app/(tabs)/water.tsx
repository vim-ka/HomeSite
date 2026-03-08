import { ScrollView, View, Text, TouchableOpacity, StyleSheet, RefreshControl } from "react-native";
import { useTranslation } from "react-i18next";
import { useSettings, useSettingUpdate } from "../../src/hooks/useSettings";
import { useDashboard } from "../../src/hooks/useDashboard";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";
import Toggle from "../../src/components/Toggle";
import TempSlider from "../../src/components/TempSlider";
import StatusBadge from "../../src/components/StatusBadge";
import { colors } from "../../src/theme/colors";

const DAYS = [1, 2, 3, 4, 5, 6, 7];

function fmt(v: number | null): string {
  return v != null ? v.toFixed(1) : "—";
}

export default function WaterScreen() {
  const { t } = useTranslation();
  const { data: settings, isLoading, refetch } = useSettings();
  const { data: dashboard } = useDashboard();
  const update = useSettingUpdate();

  const s = settings ?? {};
  const ihbAuto = s.watersupply_ihb_automode === "1";
  const tenAuto = s.watersupply_ihb_teh_automode === "1";
  const almEnabled = s.watersupply_ihb_alm_mode === "1";
  const almDays = (s.watersupply_alm_days ?? "").split(",").filter(Boolean);

  const toggleDay = (day: number) => {
    const ds = new Set(almDays.map(Number));
    if (ds.has(day)) ds.delete(day);
    else ds.add(day);
    update("watersupply_alm_days", Array.from(ds).sort().join(","));
  };

  if (isLoading) {
    return (
      <View style={styles.center}>
        <Text style={styles.loadingText}>{t("common.loading")}</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={refetch} />}
    >
      {/* Current Readings */}
      <Section title={t("waterSupply.currentReadings")}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {dashboard?.water_supply.map((w) => (
            <Card key={w.type} style={styles.readingCard}>
              <Text style={styles.readingTitle}>{w.type}</Text>
              <Text style={[styles.readingValue, { color: colors.sky[500] }]}>
                {w.temp_fact != null ? `${fmt(w.temp_fact)}°` : "—"}
              </Text>
              <View style={{ marginTop: 6 }}>
                <StatusBadge on={w.pump === "1"} labelOn={t("dashboard.on")} labelOff={t("dashboard.off")} />
              </View>
            </Card>
          ))}
        </ScrollView>
      </Section>

      {/* IHB + Pumps */}
      <View style={styles.row}>
        <Card style={styles.flex1}>
          <Text style={styles.sectionTitle}>{t("waterSupply.ihb")}</Text>
          <Toggle
            label={t("waterSupply.ihbAutoMode")}
            value={ihbAuto}
            onValueChange={(v) => update("watersupply_ihb_automode", v ? "1" : "0")}
          />
          <Toggle
            label={t("waterSupply.ihbPump")}
            value={s.watersupply_ihb_pump === "1"}
            onValueChange={(v) => update("watersupply_ihb_pump", v ? "1" : "0")}
            disabled={ihbAuto}
          />
          <TempSlider
            label={t("waterSupply.ihbTemp")}
            value={parseInt(s.watersupply_ihb_temp ?? "45")}
            min={30}
            max={65}
            onValueChange={(v) => update("watersupply_ihb_temp", String(v))}
            disabled={ihbAuto}
          />
        </Card>

        <Card style={[styles.flex1, { marginLeft: 8 }]}>
          <Text style={styles.sectionTitle}>{t("waterSupply.pumps")}</Text>
          <Toggle
            label={t("waterSupply.coldPump")}
            value={s.watersupply_pump === "1"}
            onValueChange={(v) => update("watersupply_pump", v ? "1" : "0")}
          />
          <Toggle
            label={t("waterSupply.hotPump")}
            value={s.watersupply_pump_hot === "1"}
            onValueChange={(v) => update("watersupply_pump_hot", v ? "1" : "0")}
          />
        </Card>
      </View>

      {/* TEN + Anti-Legionella */}
      <View style={styles.row}>
        <Card style={styles.flex1}>
          <Text style={styles.sectionTitle}>{t("waterSupply.ten")}</Text>
          <Toggle
            label={t("waterSupply.tenAutoMode")}
            value={tenAuto}
            onValueChange={(v) => update("watersupply_ihb_teh_automode", v ? "1" : "0")}
          />
          <TempSlider
            label={t("waterSupply.tenDelay")}
            value={parseInt(s.watersupply_ihb_teh_heating_delay ?? "120")}
            min={30}
            max={300}
            step={10}
            unit={` ${t("common.min")}`}
            onValueChange={(v) => update("watersupply_ihb_teh_heating_delay", String(v))}
            disabled={!tenAuto}
          />
          <Toggle
            label={t("waterSupply.tenPower")}
            value={s.watersupply_ihb_teh_power === "1"}
            onValueChange={(v) => update("watersupply_ihb_teh_power", v ? "1" : "0")}
            disabled={tenAuto}
          />
        </Card>

        <Card style={[styles.flex1, { marginLeft: 8 }]}>
          <Text style={styles.sectionTitle}>{t("waterSupply.antiLegionella")}</Text>
          <Toggle
            label={t("waterSupply.almEnabled")}
            value={almEnabled}
            onValueChange={(v) => update("watersupply_ihb_alm_mode", v ? "1" : "0")}
          />
          <TempSlider
            label={t("waterSupply.almTemp")}
            value={parseInt(s.watersupply_alm_temp ?? "60")}
            min={55}
            max={75}
            onValueChange={(v) => update("watersupply_alm_temp", String(v))}
            disabled={!almEnabled}
          />
          {/* Day buttons */}
          <Text style={styles.smallLabel}>{t("waterSupply.almDays")}</Text>
          <View style={styles.daysRow}>
            {DAYS.map((d) => {
              const active = almDays.includes(String(d));
              return (
                <TouchableOpacity
                  key={d}
                  style={[styles.dayBtn, active && styles.dayBtnActive]}
                  onPress={() => toggleDay(d)}
                  disabled={!almEnabled}
                >
                  <Text style={[styles.dayText, active && styles.dayTextActive]}>
                    {t(`days.${d}`)}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
          <TempSlider
            label={t("waterSupply.almDuration")}
            value={parseInt(s.watersupply_alm_duration ?? "30")}
            min={10}
            max={120}
            step={5}
            unit={` ${t("common.min")}`}
            onValueChange={(v) => update("watersupply_alm_duration", String(v))}
            disabled={!almEnabled}
          />
        </Card>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray[100] },
  content: { padding: 16, paddingBottom: 32 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  loadingText: { color: colors.gray[500] },
  row: { flexDirection: "row", marginBottom: 12 },
  flex1: { flex: 1 },
  sectionTitle: { fontSize: 14, fontWeight: "700", color: colors.gray[800], marginBottom: 6 },
  readingCard: { width: 130, marginRight: 10, alignItems: "center", paddingVertical: 12 },
  readingTitle: { fontSize: 13, fontWeight: "600", color: colors.gray[700], marginBottom: 4 },
  readingValue: { fontSize: 24, fontWeight: "800" },
  smallLabel: { fontSize: 13, color: colors.gray[600], marginTop: 8, marginBottom: 6 },
  daysRow: { flexDirection: "row", flexWrap: "wrap", gap: 4 },
  dayBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: colors.gray[100],
    borderWidth: 1,
    borderColor: colors.gray[200],
  },
  dayBtnActive: {
    backgroundColor: colors.primary[600],
    borderColor: colors.primary[600],
  },
  dayText: { fontSize: 12, color: colors.gray[600] },
  dayTextActive: { color: colors.white, fontWeight: "600" },
});
