import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { BotCyclesResponse, BotStatus } from "./botApi";

const STORAGE_KEY = "stamina_bot_state";

type BotState = {
  status: BotStatus | null;
  cycles: BotCyclesResponse | null;
  lastUpdated: string | null;
};

function loadFromStorage(): BotState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw) as BotState;
    }
  } catch {
    // Ignore storage errors
  }
  return { status: null, cycles: null, lastUpdated: null };
}

const initialState: BotState = loadFromStorage();

const botStateSlice = createSlice({
  name: "botState",
  initialState,
  reducers: {
    cacheBotStatus(state, action: PayloadAction<BotStatus>) {
      state.status = action.payload;
      state.lastUpdated = new Date().toISOString();
      persist(state);
    },
    cacheBotCycles(state, action: PayloadAction<BotCyclesResponse>) {
      state.cycles = action.payload;
      state.lastUpdated = new Date().toISOString();
      persist(state);
    },
    clearBotCache(state) {
      state.status = null;
      state.cycles = null;
      state.lastUpdated = null;
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        // Ignore storage errors
      }
    },
  },
});

function persist(state: BotState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore storage errors
  }
}

export const { cacheBotStatus, cacheBotCycles, clearBotCache } = botStateSlice.actions;
export default botStateSlice.reducer;