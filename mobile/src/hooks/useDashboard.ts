import { useQuery } from "@tanstack/react-query";
import api from "../api/client";

export interface ClimateRoom {
  room: string;
  temperature: number | null;
  humidity: number | null;
  pressure: number | null;
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
  temp_set: number | null;
  temp_fact: number | null;
  pump: string | null;
}

export interface DashboardData {
  climate: ClimateRoom[];
  heating: HeatingCircuit[];
  water_supply: WaterSupplyItem[];
}

export function useDashboard() {
  return useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const { data } = await api.get("/sensors/dashboard");
      return data;
    },
    refetchInterval: 15000,
  });
}
