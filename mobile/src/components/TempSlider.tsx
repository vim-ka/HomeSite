import { View, Text, StyleSheet } from "react-native";
import Slider from "@react-native-community/slider";
import { useTheme } from "../hooks/useTheme";

interface TempSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit?: string;
  onValueChange: (val: number) => void;
  disabled?: boolean;
}

export default function TempSlider({
  label,
  value,
  min,
  max,
  step = 1,
  unit = "°C",
  onValueChange,
  disabled,
}: TempSliderProps) {
  const { colors } = useTheme();
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={[{ fontSize: 13, color: colors.gray[800], flex: 1, marginRight: 8 }, disabled && { color: colors.gray[400] }]} numberOfLines={1}>
          {label}
        </Text>
        <Text style={[{ fontSize: 16, fontWeight: "700", color: colors.orange[500] }, disabled && { color: colors.gray[400] }]}>
          {value}{unit}
        </Text>
      </View>
      <Slider
        value={value}
        minimumValue={min}
        maximumValue={max}
        step={step}
        onSlidingComplete={onValueChange}
        disabled={disabled}
        minimumTrackTintColor={disabled ? colors.gray[300] : colors.primary[600]}
        maximumTrackTintColor={colors.gray[200]}
        thumbTintColor={disabled ? colors.gray[400] : colors.primary[600]}
        style={styles.slider}
      />
      <View style={styles.bounds}>
        <Text style={{ fontSize: 10, color: colors.gray[400] }}>{min}{unit}</Text>
        <Text style={{ fontSize: 10, color: colors.gray[400] }}>{max}{unit}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingVertical: 6 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  slider: { width: "100%", height: 36 },
  bounds: { flexDirection: "row", justifyContent: "space-between" },
});
