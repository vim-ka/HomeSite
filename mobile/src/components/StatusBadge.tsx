import { View, Text, StyleSheet } from "react-native";
import { colors } from "../theme/colors";

interface StatusBadgeProps {
  on: boolean;
  labelOn?: string;
  labelOff?: string;
}

export default function StatusBadge({ on, labelOn = "ВКЛ", labelOff = "ВЫКЛ" }: StatusBadgeProps) {
  return (
    <View style={[styles.badge, on ? styles.on : styles.off]}>
      <Text style={[styles.text, on ? styles.textOn : styles.textOff]}>
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
  on: {
    backgroundColor: colors.green[100],
  },
  off: {
    backgroundColor: colors.gray[100],
  },
  text: {
    fontSize: 12,
    fontWeight: "600",
  },
  textOn: {
    color: colors.green[700],
  },
  textOff: {
    color: colors.gray[500],
  },
});
