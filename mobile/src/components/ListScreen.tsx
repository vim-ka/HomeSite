import { ReactNode } from "react";
import {
  ScrollView,
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { useTranslation } from "react-i18next";
import { useTheme } from "../hooks/useTheme";
import Card from "./Card";

interface ListScreenProps {
  addLabel?: string;
  onAdd?: () => void;
  refreshing?: boolean;
  onRefresh?: () => void;
  empty?: boolean;
  emptyText?: string;
  children: ReactNode;
}

export default function ListScreen({
  addLabel,
  onAdd,
  refreshing,
  onRefresh,
  empty,
  emptyText,
  children,
}: ListScreenProps) {
  const { t } = useTranslation();
  const { colors } = useTheme();
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.gray[100] }}
      contentContainerStyle={styles.content}
      refreshControl={
        onRefresh ? (
          <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} />
        ) : undefined
      }
    >
      {onAdd && (
        <TouchableOpacity
          onPress={onAdd}
          style={[styles.addBtn, { backgroundColor: colors.primary[600] }]}
        >
          <Ionicons name="add" size={18} color="#ffffff" />
          <Text style={styles.addBtnText}>{addLabel ?? t("admin.add")}</Text>
        </TouchableOpacity>
      )}
      {empty ? (
        <Card>
          <Text style={[styles.empty, { color: colors.gray[400] }]}>
            {emptyText ?? t("admin.noItems")}
          </Text>
        </Card>
      ) : (
        children
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: 16, paddingBottom: 40 },
  addBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    paddingVertical: 12,
    borderRadius: 10,
    marginBottom: 16,
  },
  addBtnText: { color: "#ffffff", fontSize: 15, fontWeight: "700" },
  empty: { fontSize: 14, textAlign: "center", paddingVertical: 16 },
});
