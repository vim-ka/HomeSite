import { View, Text, StyleSheet, type ViewProps } from "react-native";
import { colors } from "../theme/colors";

interface SectionProps extends ViewProps {
  title: string;
  children: React.ReactNode;
}

export default function Section({ title, children, style, ...props }: SectionProps) {
  return (
    <View style={[styles.container, style]} {...props}>
      <Text style={styles.title}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 20,
  },
  title: {
    fontSize: 18,
    fontWeight: "700",
    color: colors.gray[800],
    marginBottom: 12,
  },
});
