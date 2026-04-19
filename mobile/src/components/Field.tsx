import { ReactNode } from "react";
import { View, Text, TextInput, StyleSheet, TouchableOpacity } from "react-native";
import { useTheme } from "../hooks/useTheme";

interface FieldProps {
  label: string;
  children: ReactNode;
}

export function Field({ label, children }: FieldProps) {
  const { colors } = useTheme();
  return (
    <View>
      <Text style={[styles.label, { color: colors.gray[600] }]}>{label}</Text>
      {children}
    </View>
  );
}

interface TextFieldProps {
  label: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  keyboardType?: "default" | "numeric" | "email-address" | "url";
  secure?: boolean;
  autoCapitalize?: "none" | "sentences" | "words" | "characters";
}

export function TextField({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType = "default",
  secure = false,
  autoCapitalize = "sentences",
}: TextFieldProps) {
  const { colors } = useTheme();
  return (
    <Field label={label}>
      <TextInput
        style={[
          styles.input,
          { borderColor: colors.gray[200], backgroundColor: colors.gray[50], color: colors.gray[800] },
        ]}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.gray[400]}
        keyboardType={keyboardType}
        secureTextEntry={secure}
        autoCapitalize={autoCapitalize}
        autoCorrect={false}
      />
    </Field>
  );
}

interface PickerOption {
  value: string;
  label: string;
}

interface PickerFieldProps {
  label: string;
  value: string;
  options: PickerOption[];
  onChange: (v: string) => void;
  emptyLabel?: string;
}

export function PickerField({
  label,
  value,
  options,
  onChange,
  emptyLabel,
}: PickerFieldProps) {
  const { colors } = useTheme();
  const opts = emptyLabel
    ? [{ value: "", label: emptyLabel }, ...options]
    : options;
  return (
    <Field label={label}>
      <View style={styles.pickerWrap}>
        {opts.map((o) => (
          <TouchableOpacity
            key={o.value || "__empty"}
            style={[
              styles.pickerChip,
              { borderColor: colors.gray[200], backgroundColor: colors.gray[50] },
              value === o.value && {
                backgroundColor: colors.primary[600],
                borderColor: colors.primary[600],
              },
            ]}
            onPress={() => onChange(o.value)}
          >
            <Text
              style={[
                styles.pickerText,
                { color: colors.gray[600] },
                value === o.value && { color: "#ffffff", fontWeight: "700" },
              ]}
              numberOfLines={1}
            >
              {o.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </Field>
  );
}

const styles = StyleSheet.create({
  label: { fontSize: 12, fontWeight: "600", marginBottom: 6 },
  input: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
    fontSize: 14,
  },
  pickerWrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  pickerChip: {
    borderWidth: 1,
    borderRadius: 16,
    paddingVertical: 6,
    paddingHorizontal: 12,
    maxWidth: "100%",
  },
  pickerText: { fontSize: 12, fontWeight: "500" },
});
