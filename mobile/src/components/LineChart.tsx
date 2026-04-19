import { useMemo } from "react";
import { View, Text, StyleSheet } from "react-native";
import Svg, { Polyline, Line as SvgLine, Text as SvgText } from "react-native-svg";
import { useTheme } from "../hooks/useTheme";

export interface LineDataset {
  label: string;
  data: (number | null)[];
  color: string;
}

interface LineChartProps {
  /** X-axis labels (one per data point). Only a few are rendered on the axis. */
  labels: string[];
  datasets: LineDataset[];
  unit?: string;
  height?: number;
  width: number;
}

const LEFT_PAD = 38;
const RIGHT_PAD = 10;
const TOP_PAD = 12;
const BOTTOM_PAD = 22;

/**
 * Compact multi-series line chart for mobile.
 * Renders SVG polylines with Y-axis ticks, a Y-grid, and X-axis label samples.
 */
export default function LineChart({
  labels,
  datasets,
  unit = "",
  height = 220,
  width,
}: LineChartProps) {
  const { colors, isDark } = useTheme();

  const { minY, maxY } = useMemo(() => {
    let min = Infinity;
    let max = -Infinity;
    for (const ds of datasets) {
      for (const v of ds.data) {
        if (v == null || !Number.isFinite(v)) continue;
        if (v < min) min = v;
        if (v > max) max = v;
      }
    }
    if (!Number.isFinite(min) || !Number.isFinite(max)) {
      return { minY: 0, maxY: 1 };
    }
    if (min === max) {
      return { minY: min - 1, maxY: max + 1 };
    }
    // Padding above/below so the line doesn't stick to edges
    const pad = (max - min) * 0.08;
    return { minY: min - pad, maxY: max + pad };
  }, [datasets]);

  const n = labels.length;
  const innerW = Math.max(0, width - LEFT_PAD - RIGHT_PAD);
  const innerH = Math.max(0, height - TOP_PAD - BOTTOM_PAD);

  const xFor = (i: number) => (n <= 1 ? LEFT_PAD : LEFT_PAD + (i * innerW) / (n - 1));
  const yFor = (v: number) =>
    TOP_PAD + innerH - ((v - minY) / (maxY - minY || 1)) * innerH;

  const gridColor = isDark ? "#334155" : "#e5e7eb";
  const axisText = isDark ? "#9ca3af" : "#6b7280";

  const yTicks = 4;
  const yTickValues = Array.from({ length: yTicks + 1 }, (_, i) =>
    minY + ((maxY - minY) * i) / yTicks,
  );

  const xTicksToShow = 4;
  const xTickIndices = Array.from({ length: xTicksToShow + 1 }, (_, i) =>
    n <= 1 ? 0 : Math.round((i * (n - 1)) / xTicksToShow),
  );

  const buildPoints = (data: (number | null)[]) => {
    // Polyline ignores null → break line into segments between null gaps
    const segments: string[] = [];
    let buf: string[] = [];
    for (let i = 0; i < data.length; i++) {
      const v = data[i];
      if (v == null || !Number.isFinite(v)) {
        if (buf.length > 0) {
          segments.push(buf.join(" "));
          buf = [];
        }
        continue;
      }
      buf.push(`${xFor(i).toFixed(1)},${yFor(v).toFixed(1)}`);
    }
    if (buf.length > 0) segments.push(buf.join(" "));
    return segments;
  };

  if (n === 0 || datasets.length === 0) {
    return (
      <View style={{ height }}>
        <Text style={[styles.empty, { color: colors.gray[400] }]}>—</Text>
      </View>
    );
  }

  return (
    <View>
      <Svg width={width} height={height}>
        {/* Y grid + tick labels */}
        {yTickValues.map((v, i) => {
          const y = yFor(v);
          return (
            <SvgLine
              key={`g-${i}`}
              x1={LEFT_PAD}
              x2={width - RIGHT_PAD}
              y1={y}
              y2={y}
              stroke={gridColor}
              strokeWidth={1}
              strokeDasharray="3,3"
            />
          );
        })}
        {yTickValues.map((v, i) => (
          <SvgText
            key={`yt-${i}`}
            x={LEFT_PAD - 4}
            y={yFor(v) + 3}
            fontSize="9"
            fill={axisText}
            textAnchor="end"
          >
            {v.toFixed(Math.abs(maxY - minY) < 5 ? 1 : 0)}
            {unit}
          </SvgText>
        ))}

        {/* X-axis tick labels */}
        {xTickIndices.map((idx, i) => (
          <SvgText
            key={`xt-${i}`}
            x={xFor(idx)}
            y={height - 6}
            fontSize="9"
            fill={axisText}
            textAnchor="middle"
          >
            {labels[idx] ?? ""}
          </SvgText>
        ))}

        {/* Series */}
        {datasets.map((ds) =>
          buildPoints(ds.data).map((seg, i) => (
            <Polyline
              key={`${ds.label}-${i}`}
              points={seg}
              fill="none"
              stroke={ds.color}
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          )),
        )}
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  empty: {
    textAlign: "center",
    paddingVertical: 20,
    fontSize: 13,
  },
});
