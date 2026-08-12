import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import { usersConfigApiUrl } from "../config";

// In production the backend is reached through the nginx proxy at a RELATIVE
// path (/api). This keeps internal hosts/ports out of the browser bundle.
// In local dev (Vite) the proxy rewrites /api -> http://localhost:8080.
//
// Demo vs real is NOT a separate URL: pass `demo` (bool) in the request.
// When omitted, the backend falls back to its ETORO_DEMO config.

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

    // ── Trading (demo vs real via the `demo` query param) ──
    openByAmount: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; amount: number; demo?: boolean }>({
      query: ({ demo, ...params }) => ({
        url: `/etoro/trading/open-by-amount`,
        params: { ...params, ...(demo !== undefined ? { demo } : {}) },
      }),
    }),

    openByUnits: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; units: number; demo?: boolean }>({
      query: ({ demo, ...params }) => ({
        url: `/etoro/trading/open-by-units`,
        params: { ...params, ...(demo !== undefined ? { demo } : {}) },
      }),
    }),

    closePosition: builder.mutation<any, { userId: string; positionId: number; unitsToDeduct?: number | null; demo?: boolean }>({
      query: ({ userId, positionId, unitsToDeduct, demo }) => ({
        url: `/etoro/trading/close-position/${positionId}`,
        params: {
          userId,
          ...(unitsToDeduct !== undefined && unitsToDeduct !== null ? { unitsToDeduct } : {}),
          ...(demo !== undefined ? { demo } : {}),
        },
      }),
    }),

    cancelOrder: builder.mutation<any, { userId: string; orderId: number; demo?: boolean }>({
      query: ({ orderId, demo, ...params }) => ({
        url: `/etoro/trading/cancel-order/${orderId}`,
        method: "DELETE",
        params: { ...params, ...(demo !== undefined ? { demo } : {}) },
      }),
    }),

    // ── Portfolio & P&L (demo vs real via the `demo` query param) ──
    getPortfolio: builder.query<any, { userId: string; demo?: boolean }>({
      query: ({ userId, demo }) =>
        `/etoro/portfolio?userId=${userId}${demo !== undefined ? `&demo=${demo}` : ""}`,
    }),

    getPnl: builder.query<any, { userId: string; demo?: boolean }>({
      query: ({ userId, demo }) =>
        `/etoro/portfolio/pnl?userId=${userId}${demo !== undefined ? `&demo=${demo}` : ""}`,
    }),

    getTradeHistory: builder.query<any, { userId: string; minDate: string; page?: number; pageSize?: number }>({
      query: ({ userId, minDate, page = 1, pageSize = 20 }) =>
        `/etoro/portfolio/trade-history?userId=${userId}&minDate=${minDate}&page=${page}&pageSize=${pageSize}`,
    }),

    // ── Backward-compatible demo variants (explicit demo: true) ──
    demoOpenByAmount: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; amount: number }>({
      query: (params) => ({
        url: `/etoro/trading/open-by-amount`,
        params: { ...params, demo: true },
      }),
    }),

    demoOpenByUnits: builder.mutation<any, { userId: string; instrumentId: number; isBuy: boolean; leverage?: number; units: number }>({
      query: (params) => ({
        url: `/etoro/trading/open-by-units`,
        params: { ...params, demo: true },
      }),
    }),

    demoClosePosition: builder.mutation<any, { userId: string; positionId: number; unitsToDeduct?: number | null }>({
      query: ({ userId, positionId, unitsToDeduct }) => ({
        url: `/etoro/trading/close-position/${positionId}`,
        params: {
          userId,
          demo: true,
          ...(unitsToDeduct !== undefined && unitsToDeduct !== null ? { unitsToDeduct } : {}),
        },
      }),
    }),

    getDemoPortfolio: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio?userId=${userId}&demo=true`,
    }),

    getDemoPnl: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio/pnl?userId=${userId}&demo=true`,
    }),

    getRealPnl: builder.query<any, { userId: string }>({
      query: ({ userId }) => `/etoro/portfolio/pnl?userId=${userId}&demo=false`,
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
  useGetPnlQuery,
  useGetRealPnlQuery,
  useGetDemoPnlQuery,
  useGetTradeHistoryQuery,
  useLazySearchInstrumentsQuery,
  useLazyGetInstrumentRatesQuery,
  useLazyGetCandlesQuery,
  useLazyGetPortfolioQuery,
  useLazyGetDemoPortfolioQuery,
  useLazyGetPnlQuery,
  useLazyGetRealPnlQuery,
  useLazyGetDemoPnlQuery,
  useLazyGetTradeHistoryQuery,
} = etoroApi;