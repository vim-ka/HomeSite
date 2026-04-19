import { ReactNode } from "react";
import {
  Modal,
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useTranslation } from "react-i18next";
import { useTheme } from "../hooks/useTheme";

interface FormModalProps {
  visible: boolean;
  title: string;
  onClose: () => void;
  onSave?: () => void;
  saveLabel?: string;
  saveDisabled?: boolean;
  children: ReactNode;
}

export default function FormModal({
  visible,
  title,
  onClose,
  onSave,
  saveLabel,
  saveDisabled,
  children,
}: FormModalProps) {
  const { t } = useTranslation();
  const { colors } = useTheme();

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.overlay}
      >
        <View style={[styles.container, { backgroundColor: colors.white }]}>
          <View style={[styles.header, { borderBottomColor: colors.gray[200] }]}>
            <Text style={[styles.title, { color: colors.gray[800] }]}>{title}</Text>
            <TouchableOpacity onPress={onClose} style={styles.closeBtn}>
              <Text style={[styles.closeText, { color: colors.gray[500] }]}>✕</Text>
            </TouchableOpacity>
          </View>
          <ScrollView
            style={styles.body}
            contentContainerStyle={styles.bodyContent}
            keyboardShouldPersistTaps="handled"
          >
            {children}
          </ScrollView>
          <View style={[styles.footer, { borderTopColor: colors.gray[200] }]}>
            <TouchableOpacity
              onPress={onClose}
              style={[styles.btn, { backgroundColor: colors.gray[200] }]}
            >
              <Text style={[styles.btnText, { color: colors.gray[700] }]}>
                {t("admin.cancel")}
              </Text>
            </TouchableOpacity>
            {onSave && (
              <TouchableOpacity
                onPress={onSave}
                disabled={saveDisabled}
                style={[
                  styles.btn,
                  { backgroundColor: saveDisabled ? colors.gray[300] : colors.primary[600] },
                ]}
              >
                <Text style={[styles.btnText, { color: "#ffffff" }]}>
                  {saveLabel ?? t("admin.save")}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.5)",
    justifyContent: "center",
    alignItems: "center",
    padding: 16,
  },
  container: {
    width: "100%",
    maxWidth: 420,
    maxHeight: "85%",
    borderRadius: 16,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: 16,
    borderBottomWidth: 1,
  },
  title: { fontSize: 17, fontWeight: "700", flex: 1 },
  closeBtn: { paddingLeft: 12, paddingVertical: 4 },
  closeText: { fontSize: 22, fontWeight: "600" },
  body: { flexShrink: 1 },
  bodyContent: { padding: 16, gap: 12 },
  footer: {
    flexDirection: "row",
    gap: 10,
    padding: 12,
    borderTopWidth: 1,
  },
  btn: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 10,
    alignItems: "center",
  },
  btnText: { fontSize: 15, fontWeight: "700" },
});
