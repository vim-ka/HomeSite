import { create } from "zustand";

interface PendingState {
  localPending: number;
  increment: (n: number) => void;
  syncFromServer: (serverPending: number) => void;
}

export const usePendingCommands = create<PendingState>((set) => ({
  localPending: 0,
  increment: (n) => set((s) => ({ localPending: s.localPending + n })),
  syncFromServer: (serverPending) => set({ localPending: serverPending }),
}));
