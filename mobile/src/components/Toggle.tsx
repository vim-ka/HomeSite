import { Switch, View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";

interface ToggleProps {
  label: string;
  value: boolean;
  onValueChange: (val: boolean) => void;
  disabled?: boolean;
  hint?: string;
}

export default function Toggle({ label, value, onValueChange, disabled, hint }: ToggleProps) {
  return (
    <View style={styles.container}>
      <View style={styles.labelContainer}>
        <Text style={[styles.label, disabled && styles.disabled]} numberOfLines={2}>{label}</Text>
        {hint && <Text style={styles.hint} numberOfLines={1}>{hint}</Text>}
      </View>
      <Switch
        value={value}
        onValueChange={onValueChange}
        disabled={disabled}
        trackColor={{ false: colors.gray[300], true: colors.primary[200] }}
        thumbColor={value ? colors.primary[600] : colors.gray[100]}
        style={styles.switch}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: 8,
  },
  labelContainer: {
    flex: 1,
    marginRight: 8,
  },
  label: {
    fontSize: 13,
    color: colors.gray[800],
  },
  disabled: {
    color: colors.gray[400],
  },
  hint: {
    fontSize: 11,
    color: colors.gray[400],
    marginTop: 2,
  },
  switch: {
    transform: [{ scaleX: 0.85 }, { scaleY: 0.85 }],
  },
});
