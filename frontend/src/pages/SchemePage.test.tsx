import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { makeState } from "@/scheme/testing";
import SchemePage from "./SchemePage";

vi.mock("@/scheme/useSchemeState", () => ({
  useSchemeState: () => ({ data: withAlarm(), isLoading: false, refetch: vi.fn() }),
  useSchemeRefreshOnWs: () => {},
}));

function withAlarm() {
  const s = makeState();
  s.alarms = [{ level: "ERROR", code: "pressure_low", text: "Давление 0.92 бар ниже нормы 1" }];
  s.sync.unsynced = ["heating_boiler_temp"];
  return s;
}

describe("SchemePage", () => {
  it("renders the scheme, alarms and unsynced counter", () => {
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter><SchemePage /></MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByRole("img", { name: "Схема котельной" })).toBeInTheDocument();
    expect(screen.getByText("Давление 0.92 бар ниже нормы 1")).toBeInTheDocument();
    expect(screen.getByText(/Не синхронизировано: 1/)).toBeInTheDocument();
  });
});
