import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";

export interface ClimateRoom {
  room: string;
  temperature?: number;
  humidity?: number;
  pressure?: number;
}

export interface HeatingCircuit {
  circuit: string;
  temp_set: number | null;
  temp_supply: number | null;
  temp_return: number | null;
  pressure: number | null;
  pump: string | null;
  pza_mode: boolean;
  pza_curve: number | null;
  pza_capable: boolean;
}

export interface WaterSupplyItem {
  type: string;
  temp_set: number | null;
  temp_fact: number | null;
  pressure: number | null;
  pump: string | null;
}

export interface Stats24h {
  whk24: number;
  whb24: number;
  whr24: number;
  whf24: number;
  avght24: number;
}

export interface DashboardData {
  climate: ClimateRoom[];
  heating: HeatingCircuit[];
  water_supply: WaterSupplyItem[];
  stats: Stats24h;
}

export function useDashboard() {
  return useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const { data } = await api.get("/sensors/dashboard");
      return data;
    },
    refetchInterval: 30_000,
  });
}
