import { ScrollView, View, Text, StyleSheet, RefreshControl } from "react-native";
import { useTranslation } from "react-i18next";
import { useSettings, useSettingUpdate } from "../../src/hooks/useSettings";
import { useDashboard } from "../../src/hooks/useDashboard";
import Card from "../../src/components/Card";
import Section from "../../src/components/Section";
import Toggle from "../../src/components/Toggle";
import TempSlider from "../../src/components/TempSlider";
import StatusBadge from "../../src/components/StatusBadge";
import { colors } from "../../src/theme/colors";

function fmt(v: number | null): string {
  return v != null ? v.toFixed(1) : "—";
}

export default function HeatingScreen() {
  const { t } = useTranslation();
  const { data: settings, isLoading, refetch } = useSettings();
  const { data: dashboard } = useDashboard();
  const update = useSettingUpdate();

  const s = settings ?? {};
  const boilerAuto = s.heating_boiler_automode === "1";
  const boilerPower = s.heating_boiler_power === "1";
  const radPZA = s.heating_radiator_wbm === "1";
  const floorPZA = s.heating_floorheating_wbm === "1";
  const schedEnabled = s.heating_schedule_enabled === "1";
  const autofillEnabled = s.heating_autofill_enabled === "1";

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
      {/* Circuit Status */}
      <Section title={t("heating.circuitsStatus")}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false}>
          {dashboard?.heating.map((c) => (
            <Card key={c.circuit} style={styles.circuitCard}>
              <Text style={styles.circuitTitle}>{c.circuit}</Text>
              <Text style={styles.circuitTemp}>
                {c.temp_supply != null ? `${fmt(c.temp_supply)}°` : "—"}
              </Text>
              <Text style={styles.circuitLabel}>{t("heating.supplyTemp")}</Text>
              <View style={styles.circuitPump}>
                <StatusBadge on={c.pump === "1"} labelOn={t("dashboard.on")} labelOff={t("dashboard.off")} />
              </View>
            </Card>
          ))}
        </ScrollView>
      </Section>

      {/* Boiler + IHB */}
      <View style={styles.row}>
        <Card style={styles.flex1}>
          <Text style={styles.sectionTitle}>{t("heating.boiler")}</Text>
          <Toggle
            label={t("heating.boilerPower")}
            value={boilerPower}
            onValueChange={(v) => update("heating_boiler_power", v ? "1" : "0")}
          />
          <Toggle
            label={t("heating.autoRegulation")}
            value={boilerAuto}
            onValueChange={(v) => update("heating_boiler_automode", v ? "1" : "0")}
          />
          <TempSlider
            label={t("heating.boilerTemp")}
            value={parseInt(s.heating_boiler_temp ?? "50")}
            min={30}
            max={80}
            onValueChange={(v) => update("heating_boiler_temp", String(v))}
            disabled={boilerAuto}
          />
        </Card>

        <Card style={[styles.flex1, { marginLeft: 8 }]}>
          <Text style={styles.sectionTitle}>{t("heating.ihb")}</Text>
          <Toggle
            label={t("waterSupply.ihbAutoMode")}
            value={s.watersupply_ihb_automode === "1"}
            onValueChange={(v) => update("watersupply_ihb_automode", v ? "1" : "0")}
          />
          <Toggle
            label={t("waterSupply.ihbPump")}
            value={s.watersupply_ihb_pump === "1"}
            onValueChange={(v) => update("watersupply_ihb_pump", v ? "1" : "0")}
            disabled={s.watersupply_ihb_automode === "1"}
          />
          <TempSlider
            label={t("waterSupply.ihbTemp")}
            value={parseInt(s.watersupply_ihb_temp ?? "45")}
            min={30}
            max={65}
            onValueChange={(v) => update("watersupply_ihb_temp", String(v))}
            disabled={s.watersupply_ihb_automode === "1"}
          />
        </Card>
      </View>

      {/* Radiators */}
      <Card style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>{t("heating.radiators")}</Text>
        <Toggle
          label={t("dashboard.pump")}
          value={s.heating_radiator_pump === "1"}
          onValueChange={(v) => update("heating_radiator_pump", v ? "1" : "0")}
        />
        <Toggle
          label={t("heating.pzaMode")}
          value={radPZA}
          onValueChange={(v) => update("heating_radiator_wbm", v ? "1" : "0")}
        />
        <TempSlider
          label={t("heating.supplyTemp")}
          value={parseInt(s.heating_radiator_temp ?? "45")}
          min={20}
          max={85}
          onValueChange={(v) => update("heating_radiator_temp", String(v))}
          disabled={radPZA}
        />
        <Toggle
          label={t("heating.disableDuringIHB")}
          value={s.heating_radiator_off_ihb === "1"}
          onValueChange={(v) => update("heating_radiator_off_ihb", v ? "1" : "0")}
        />
      </Card>

      {/* Floor Heating */}
      <Card style={styles.sectionCard}>
        <Text style={styles.sectionTitle}>{t("heating.floorHeating")}</Text>
        <Toggle
          label={t("dashboard.pump")}
          value={s.heating_floorheating_pump === "1"}
          onValueChange={(v) => update("heating_floorheating_pump", v ? "1" : "0")}
        />
        <Toggle
          label={t("heating.pzaMode")}
          value={floorPZA}
          onValueChange={(v) => update("heating_floorheating_wbm", v ? "1" : "0")}
        />
        <TempSlider
          label={t("heating.supplyTemp")}
          value={parseInt(s.heating_floorheating_temp ?? "30")}
          min={20}
          max={40}
          onValueChange={(v) => update("heating_floorheating_temp", String(v))}
          disabled={floorPZA}
        />
        <Toggle
          label={t("heating.disableDuringIHB")}
          value={s.heating_floorheating_off_ihb === "1"}
          onValueChange={(v) => update("heating_floorheating_off_ihb", v ? "1" : "0")}
        />
      </Card>

      {/* Schedule + Autofill */}
      <View style={styles.row}>
        <Card style={styles.flex1}>
          <Text style={styles.sectionTitle}>{t("heating.schedule")}</Text>
          <Toggle
            label={t("heating.scheduleEnabled")}
            value={schedEnabled}
            onValueChange={(v) => update("heating_schedule_enabled", v ? "1" : "0")}
          />
          <TempSlider
            label={t("heating.scheduleDelta")}
            value={parseInt(s.heating_schedule_delta ?? "-10")}
            min={-20}
            max={0}
            onValueChange={(v) => update("heating_schedule_delta", String(v))}
            disabled={!schedEnabled}
          />
        </Card>

        <Card style={[styles.flex1, { marginLeft: 8 }]}>
          <Text style={styles.sectionTitle}>{t("heating.autofill")}</Text>
          <Toggle
            label={t("heating.autofillEnabled")}
            value={autofillEnabled}
            onValueChange={(v) => update("heating_autofill_enabled", v ? "1" : "0")}
          />
          <TempSlider
            label={t("heating.pressureMin")}
            value={parseFloat(s.heating_pressure_min ?? "1.0")}
            min={0.5}
            max={2.5}
            step={0.1}
            unit=" бар"
            onValueChange={(v) => update("heating_pressure_min", v.toFixed(1))}
            disabled={!autofillEnabled}
          />
          <TempSlider
            label={t("heating.pressureMax")}
            value={parseFloat(s.heating_pressure_max ?? "1.8")}
            min={0.5}
            max={2.5}
            step={0.1}
            unit=" бар"
            onValueChange={(v) => update("heating_pressure_max", v.toFixed(1))}
            disabled={!autofillEnabled}
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
  sectionCard: { marginBottom: 12 },
  sectionTitle: { fontSize: 14, fontWeight: "700", color: colors.gray[800], marginBottom: 6 },
  circuitCard: { width: 120, marginRight: 10, alignItems: "center", paddingVertical: 12 },
  circuitTitle: { fontSize: 13, fontWeight: "600", color: colors.gray[700], marginBottom: 6 },
  circuitTemp: { fontSize: 22, fontWeight: "800", color: colors.orange[500] },
  circuitLabel: { fontSize: 11, color: colors.gray[400], marginTop: 2 },
  circuitPump: { marginTop: 8 },
});
