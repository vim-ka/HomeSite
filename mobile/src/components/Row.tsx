import { ReactNode } from "react";
import { View, Text, TouchableOpacity, StyleSheet, Alert } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useTheme } from "../hooks/useTheme";
import Card from "./Card";

interface RowProps {
  title: string;
  subtitle?: string;
  children?: ReactNode;
  onEdit?: () => void;
  onDelete?: () => void;
  rightExtra?: ReactNode;
  confirmDelete?: boolean;
}

/** List row for admin screens — title + optional subtitle + edit/delete. */
export default function Row({
  title,
  subtitle,
  children,
  onEdit,
  onDelete,
  rightExtra,
  confirmDelete = true,
}: RowProps) {
  const { t } = useTranslation();
  const { colors } = useTheme();

  const handleDelete = () => {
    if (!onDelete) return;
    if (!confirmDelete) {
      onDelete();
      return;
    }
    Alert.alert(t("admin.deleteConfirmTitle"), t("admin.deleteConfirmMessage"), [
      { text: t("admin.cancel"), style: "cancel" },
      { text: t("admin.delete"), style: "destructive", onPress: onDelete },
    ]);
  };

  return (
    <Card style={{ marginBottom: 8 }}>
      <View style={styles.row}>
        <View style={{ flex: 1 }}>
          <Text style={[styles.title, { color: colors.gray[800] }]} numberOfLines={1}>
            {title}
          </Text>
          {subtitle && (
            <Text style={[styles.subtitle, { color: colors.gray[500] }]} numberOfLines={2}>
              {subtitle}
            </Text>
          )}
          {children}
        </View>
        {rightExtra}
        <View style={styles.actions}>
          {onEdit && (
            <TouchableOpacity onPress={onEdit} style={styles.iconBtn}>
              <Ionicons name="create-outline" size={20} color={colors.primary[600]} />
            </TouchableOpacity>
          )}
          {onDelete && (
            <TouchableOpacity onPress={handleDelete} style={styles.iconBtn}>
              <Ionicons name="trash-outline" size={20} color={colors.red[500]} />
            </TouchableOpacity>
          )}
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  title: { fontSize: 14, fontWeight: "700" },
  subtitle: { fontSize: 12, marginTop: 2 },
  actions: { flexDirection: "row", alignItems: "center" },
  iconBtn: { padding: 6 },
});
