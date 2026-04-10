export const colors = {
  primary: {
    50: "#eff6ff",
    100: "#dbeafe",
    200: "#bfdbfe",
    500: "#3b82f6",
    600: "#2563eb",
    700: "#1d4ed8",
    800: "#1e40af",
  },
  gray: {
    50: "#f9fafb",
    100: "#f3f4f6",
    200: "#e5e7eb",
    300: "#d1d5db",
    400: "#9ca3af",
    500: "#6b7280",
    600: "#4b5563",
    700: "#374151",
    800: "#1f2937",
    900: "#111827",
  },
  green: {
    100: "#dcfce7",
    500: "#22c55e",
    600: "#16a34a",
    700: "#15803d",
  },
  red: {
    100: "#fee2e2",
    500: "#ef4444",
    600: "#dc2626",
  },
  orange: {
    500: "#f97316",
  },
  sky: {
    500: "#0ea5e9",
  },
  amber: {
    50: "#fffbeb",
    100: "#fef3c7",
    600: "#d97706",
  },
  emerald: {
    500: "#10b981",
  },
  white: "#ffffff",
  black: "#000000",
} as const;

export const darkColors = {
  primary: {
    50: "#1e3a5f",
    100: "#1e3a8a",
    200: "#1e40af",
    500: "#60a5fa",
    600: "#3b82f6",
    700: "#2563eb",
    800: "#1d4ed8",
  },
  gray: {
    50: "#374151",
    100: "#1f2937",
    200: "#374151",
    300: "#4b5563",
    400: "#6b7280",
    500: "#9ca3af",
    600: "#d1d5db",
    700: "#e5e7eb",
    800: "#f3f4f6",
    900: "#f9fafb",
  },
  green: {
    100: "#14532d",
    500: "#4ade80",
    600: "#22c55e",
    700: "#16a34a",
  },
  red: {
    100: "#7f1d1d",
    500: "#f87171",
    600: "#ef4444",
  },
  orange: {
    500: "#fb923c",
  },
  sky: {
    500: "#38bdf8",
  },
  amber: {
    50: "#451a03",
    100: "#78350f",
    600: "#fbbf24",
  },
  emerald: {
    500: "#34d399",
  },
  white: "#1f2937",
  black: "#000000",
} as const;

export type ThemeColors = typeof colors;
