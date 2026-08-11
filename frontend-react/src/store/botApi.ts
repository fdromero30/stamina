import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// In production the trading core is reached through the nginx proxy at a
// RELATIVE path (/trading-core). This keeps internal hosts/ports out of the
// browser bundle. In local dev (Vite) the proxy rewrites /trading-core ->
// http://localhost:8000.
const tradingCoreUrl = import.meta.env.VITE_TRADING_CORE_URL || "/trading-core";

export type BotStatus = {
  running: boolean;
  interval_seconds: number;
  cycles_completed: number;
  last_run: string | null;
  next_run: string | null;
};

export type CycleResult = {
  status: string;
  result?: {
    evaluations?: any[];
    trades?: any[];
    adjustments?: any[];
    error?: string;
    skipped?: boolean;
    reason?: string;
  };
};

export type SignalContext = {
  candles_count: number;
  ma_short_period: number;
  ma_long_period: number;
  ma_short_value: number | null;
  ma_long_value: number | null;
  current_price: number | null;
  bid: number | null;
  ask: number | null;
  price_above_ma200: boolean | null;
  price_below_ma200: boolean | null;
  crossover: "bullish" | "bearish" | null;
  open_positions_count: number;
  max_positions: number;
  account_balance: number;
  risk_per_trade: number;
  swing_lookback: number;
  entry_price?: number;
  stop_loss?: number;
  take_profit?: number;
  units?: number;
};

export type CycleHistoryEntry = {
  timestamp: string;
  source: "auto" | "manual";
  duration_ms: number;
  status: "success" | "error";
  evaluations: any[];
  trades: any[];
  adjustments: any[];
  skipped: boolean;
  error?: string | null;
  reason?: string | null;
};

export type OpenPosition = {
  position_id: number;
  entry_price: number;
  stop_loss: number | null;
  take_profit: number | null;
  is_buy: boolean;
  breakeven_applied: boolean;
  opened_at: string;
};

export type BotCyclesResponse = {
  cycles: CycleHistoryEntry[];
  open_positions: Record<string, OpenPosition[]>;
};

export type CandlePoint = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type LinePoint = {
  time: string;
  value: number;
};

export type EngineState = {
  running: boolean;
  started_at: string | null;
  cycle_count: number;
  last_run: string | null;
  next_run: string | null;
  open_positions: Record<string, OpenPosition[]>;
  last_evaluation: any | null;
};

export type ChartData = {
  symbol: string;
  instrument_id: number;
  interval: string;
  candles: CandlePoint[];
  ma9: LinePoint[];
  ma200: LinePoint[];
  last_price: {
    bid: number | null;
    ask: number | null;
  };
  timestamp: string;
  engine: EngineState;
};

export const botApi = createApi({
  reducerPath: "botApi",
  baseQuery: fetchBaseQuery({ baseUrl: tradingCoreUrl }),
  tagTypes: ["BotStatus"],
  endpoints: (builder) => ({
    getBotStatus: builder.query<BotStatus, void>({
      query: () => "/bot/status",
      providesTags: ["BotStatus"],
    }),

    startBot: builder.mutation<{ status: string; interval_seconds: number }, void>({
      query: () => ({
        url: "/bot/start",
        method: "POST",
      }),
      invalidatesTags: ["BotStatus"],
    }),

    stopBot: builder.mutation<{ status: string; cycles_completed: number }, void>({
      query: () => ({
        url: "/bot/stop",
        method: "POST",
      }),
      invalidatesTags: ["BotStatus"],
    }),

    triggerCycle: builder.mutation<CycleResult, void>({
      query: () => ({
        url: "/bot/cycle",
        method: "POST",
      }),
      invalidatesTags: ["BotStatus"],
    }),

    evaluateStrategy: builder.mutation<any, string>({
      query: (strategyId) => ({
        url: `/bot/evaluate/${strategyId}`,
        method: "POST",
      }),
    }),

    getHealth: builder.query<{ service: string; status: string; version: string }, void>({
      query: () => "/health",
    }),

    getBotCycles: builder.query<BotCyclesResponse, void>({
      query: () => "/bot/cycles",
    }),

    getChartData: builder.query<
      ChartData,
      { userId: string; symbol: string; interval?: string; count?: number }
    >({
      query: ({ userId, symbol, interval = "5m", count = 300 }) =>
        `/chart/${encodeURIComponent(symbol)}?userId=${encodeURIComponent(userId)}&interval=${interval}&count=${count}`,
    }),
  }),
});

export const {
  useGetBotStatusQuery,
  useStartBotMutation,
  useStopBotMutation,
  useTriggerCycleMutation,
  useEvaluateStrategyMutation,
  useGetHealthQuery,
  useGetBotCyclesQuery,
  useGetChartDataQuery,
  useLazyGetBotStatusQuery,
  useLazyGetHealthQuery,
} = botApi;
