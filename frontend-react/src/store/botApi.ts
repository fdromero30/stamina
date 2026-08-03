import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

const tradingCoreUrl = import.meta.env.VITE_TRADING_CORE_URL ?? "http://localhost:8000";

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
  }),
});

export const {
  useGetBotStatusQuery,
  useStartBotMutation,
  useStopBotMutation,
  useTriggerCycleMutation,
  useEvaluateStrategyMutation,
  useGetHealthQuery,
  useLazyGetBotStatusQuery,
  useLazyGetHealthQuery,
} = botApi;