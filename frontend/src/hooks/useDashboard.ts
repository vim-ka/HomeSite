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
}

export interface WaterSupplyItem {
  type: string;
  tempSet: number | null;
  tempFact: number | null;
  pressure: number | null;
  Pump: string | null;
}

export interface Stats24h {
  heating_hours: number;
  climate_avg_temp: number | null;
  climate_avg_humidity: number | null;
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
