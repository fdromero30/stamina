import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// In production the backend is reached through the nginx proxy at a RELATIVE
// path (/api). This keeps internal hosts/ports out of the browser bundle.
// In local dev (Vite) the proxy rewrites /api -> http://localhost:8080.
const usersConfigApiUrl = import.meta.env.VITE_USERS_CONFIG_API_URL ?? "/api";

export const etoroApi = createApi({
  reducerPath: "etoroApi",
  baseQuery: fetchBaseQuery({ baseUrl: usersConfigApiUrl }),
  endpoints: (builder) => ({
    // ── Market Data ──────────────────────────────────────
    searchInstruments: builder.query<any, { userId: string; q: string; fields?: string }>({
      query: ({ userId, q, fields = "instrumentId,internalSymbolFull,displayname" }) =>
        `/etoro/market-data/search?userId=${userId}&q=${encodeURIComponent(q)}&fields=${encodeURIComponent(fields)}`,
    }),

    getInstrumentRates: builder.query<any, { userId: string; instrumentIds: number[] }>({
      query: ({ userId, instrumentIds }) =>
        `/etoro/market-data/rates?userId=${userId}&instrumentIds=${instrumentIds.join(",")}`,
    }),

    getCandles: builder.query<any, { userId: string; instrumentId: number; direction?: string; interval?: string; count?: number }>({
      query: ({ userId, instrumentId, direction = "desc", interval = "1h", count = 100 }) =>
        `/etoro/market-data/candles/${instrumentId}?userId=${userId}&direction=${direction}&interval=${interval}&count=${count}`,
    }),

    // ── Demo Trading ─────────────────────────────────────
    demoOpenByAmount: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; amount: number }>({
      query: (params) => ({
        url: `/etoro/trading/demo/open-by-amount`,
        params,
      }),
    }),

    demoOpenByUnits: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; units: number }>({
      query: (params) => ({
        url: `/etoro/trading/demo/open-by-units`,
        params,
      }),
    }),

    demoClosePosition: builder.mutation<any, { userId: string; positionId: number; unitsToDeduct?: number | null }>({
      query: ({ userId, positionId, unitsToDeduct }) => ({
        url: `/etoro/trading/demo/close-position/${positionId}`,
        params: { userId, ...(unitsToDeduct !== undefined ? { unitsToDeduct } : {}) },
      }),
    }),

    // ── Real Trading ─────────────────────────────────────
    openByAmount: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; amount: number }>({
      query: (params) => ({
        url: `/etoro/trading/open-by-amount`,
        params,
      }),
    }),

    openByUnits: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; units: number }>({
      query: (params) => ({
        url: `/etoro/trading/open-by-units`,
        params,
      }),
    }),

    closePosition: builder.mutation<any, { userId: string; positionId: number; unitsToDeduct?: number | null }>({
      query: ({ userId, positionId, unitsToDeduct }) => ({
        url: `/etoro/trading/close-position/${positionId}`,
        params: { userId, ...(unitsToDeduct !== undefined ? { unitsToDeduct } : {}) },
      }),
    }),

    cancelOrder: builder.mutation<any, { userId: string; orderId: number; demo?: boolean }>({
      query: (params) => ({
        url: `/etoro/trading/cancel-order/${params.orderId}`,
        method: "DELETE",
        params: { userId: params.userId, demo: params.demo ?? false },
      }),
    }),

    // ── Portfolio & P&L ──────────────────────────────────
    getPortfolio: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio?userId=${userId}`,
    }),

    getDemoPortfolio: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio/demo?userId=${userId}`,
    }),

    getRealPnl: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio/pnl?userId=${userId}`,
    }),

    getDemoPnl: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio/pnl/demo?userId=${userId}`,
    }),

    getTradeHistory: builder.query<any, { userId: string; minDate: string; page?: number; pageSize?: number }>({
      query: ({ userId, minDate, page = 1, pageSize = 20 }) =>
        `/etoro/portfolio/trade-history?userId=${userId}&minDate=${minDate}&page=${page}&pageSize=${pageSize}`,
    }),
  }),
});

export const {
  useSearchInstrumentsQuery,
  useGetInstrumentRatesQuery,
  useGetCandlesQuery,
  useDemoOpenByAmountMutation,
  useDemoOpenByUnitsMutation,
  useDemoClosePositionMutation,
  useOpenByAmountMutation,
  useOpenByUnitsMutation,
  useClosePositionMutation,
  useCancelOrderMutation,
  useGetPortfolioQuery,
  useGetDemoPortfolioQuery,
  useGetRealPnlQuery,
  useGetDemoPnlQuery,
  useGetTradeHistoryQuery,
  useLazySearchInstrumentsQuery,
  useLazyGetInstrumentRatesQuery,
  useLazyGetCandlesQuery,
  useLazyGetPortfolioQuery,
  useLazyGetDemoPortfolioQuery,
  useLazyGetRealPnlQuery,
  useLazyGetDemoPnlQuery,
  useLazyGetTradeHistoryQuery,
} = etoroApi;