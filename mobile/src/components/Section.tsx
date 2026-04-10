import { View, Text, type ViewProps } from "react-native";
import { useTheme } from "../hooks/useTheme";

interface SectionProps extends ViewProps {
  title: string;
  children: React.ReactNode;
}

export default function Section({ title, children, style, ...props }: SectionProps) {
  const { colors } = useTheme();
  return (
    <View style={[{ marginBottom: 20 }, style]} {...props}>
      <Text style={{ fontSize: 18, fontWeight: "700", color: colors.gray[800], marginBottom: 12 }}>
        {title}
      </Text>
      {children}
    </View>
  );
}
