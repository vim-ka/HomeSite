import { View, Text, StyleSheet } from "react-native";
import { useTheme } from "../hooks/useTheme";

interface StatusBadgeProps {
  on: boolean;
  labelOn?: string;
  labelOff?: string;
}

export default function StatusBadge({ on, labelOn = "ВКЛ", labelOff = "ВЫКЛ" }: StatusBadgeProps) {
  const { colors } = useTheme();
  return (
    <View style={[styles.badge, { backgroundColor: on ? colors.green[100] : colors.gray[100] }]}>
      <Text style={[styles.text, { color: on ? colors.green[700] : colors.gray[500] }]}>
        {on ? labelOn : labelOff}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 12,
  },
  text: {
    fontSize: 12,
    fontWeight: "600",
  },
});
