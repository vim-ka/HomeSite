import { View, type ViewProps } from "react-native";
import { useTheme } from "../hooks/useTheme";

export default function Card({ children, style, ...props }: ViewProps) {
  const { colors } = useTheme();
  return (
    <View
      style={[
        {
          backgroundColor: colors.white,
          borderRadius: 16,
          padding: 12,
          borderWidth: 1,
          borderColor: colors.gray[200],
          shadowColor: colors.black,
          shadowOffset: { width: 0, height: 1 },
          shadowOpacity: 0.05,
          shadowRadius: 3,
          elevation: 2,
          overflow: "hidden",
        },
        style,
      ]}
      {...props}
    >
      {children}
    </View>
  );
}
