import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { ApiKeyRow, AppUser, CreateApiKeyRequest, CreateStrategyRequest, CreateUserRequest, LoginRequest, MLStrategy, RevealedKeyResponse, StopLossType, StrategyConfig, UpdateStrategyRequest } from "../types";

const usersConfigApiUrl = import.meta.env.VITE_USERS_CONFIG_API_URL ?? "http://localhost:8080";

export const usersApi = createApi({
  reducerPath: "usersApi",
  baseQuery: fetchBaseQuery({ baseUrl: usersConfigApiUrl }),
  tagTypes: ["Users", "ApiKeys", "Strategies", "StopLossTypes", "MLStrategies"],
  endpoints: (builder) => ({
    // -------- Users --------
    getUsers: builder.query<AppUser[], void>({
      query: () => "/users",
      providesTags: ["Users"],
    }),

    createUser: builder.mutation<AppUser, CreateUserRequest>({
      query: (body) => ({
        url: "/users",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Users"],
    }),

    login: builder.mutation<AppUser, LoginRequest>({
      query: (body) => ({
        url: "/users/login",
        method: "POST",
        body,
      }),
    }),

    // -------- API Keys --------
    getApiKeys: builder.query<ApiKeyRow[], string>({
      query: (userId) => `/api-keys?userId=${userId}`,
      providesTags: ["ApiKeys"],
    }),

    createApiKey: builder.mutation<ApiKeyRow, { userId: string; label: string; broker: string; publicKey: string; privateKey: string }>({
      query: (body) => ({
        url: "/api-keys",
        method: "POST",
        body,
      }),
      invalidatesTags: ["ApiKeys"],
    }),

    revealApiKey: builder.mutation<RevealedKeyResponse, { id: string; userId: string }>({
      query: ({ id, userId }) => ({
        url: `/api-keys/${id}/reveal?userId=${userId}`,
        method: "POST",
      }),
    }),

    deleteApiKey: builder.mutation<void, { id: string; userId: string }>({
      query: ({ id, userId }) => ({
        url: `/api-keys/${id}?userId=${userId}`,
        method: "DELETE",
      }),
      invalidatesTags: ["ApiKeys"],
    }),

    // -------- Strategy Configs --------
    getUserStrategies: builder.query<StrategyConfig[], string>({
      query: (userId) => `/strategies?userId=${userId}`,
      providesTags: ["Strategies"],
    }),

    getStrategyById: builder.query<StrategyConfig, string>({
      query: (id) => `/strategies/${id}`,
      providesTags: (_result, _error, id) => [{ type: "Strategies", id }],
    }),

    createStrategy: builder.mutation<StrategyConfig, CreateStrategyRequest>({
      query: (body) => ({
        url: "/strategies",
        method: "POST",
        body,
      }),
      invalidatesTags: ["Strategies"],
    }),

    updateStrategy: builder.mutation<StrategyConfig, { id: string; body: UpdateStrategyRequest }>({
      query: ({ id, body }) => ({
        url: `/strategies/${id}`,
        method: "PUT",
        body,
      }),
      invalidatesTags: ["Strategies"],
    }),

    deleteStrategy: builder.mutation<void, string>({
      query: (id) => ({
        url: `/strategies/${id}`,
        method: "DELETE",
      }),
      invalidatesTags: ["Strategies"],
    }),

    // -------- Catalogs --------
    getStopLossTypes: builder.query<StopLossType[], void>({
      query: () => "/strategies/stop-loss-types",
      providesTags: ["StopLossTypes"],
    }),

    getMLStrategies: builder.query<MLStrategy[], void>({
      query: () => "/strategies/ml-strategies",
      providesTags: ["MLStrategies"],
    }),
  }),
});

export const {
  useGetUsersQuery,
  useCreateUserMutation,
  useLoginMutation,
  useGetApiKeysQuery,
  useCreateApiKeyMutation,
  useRevealApiKeyMutation,
  useDeleteApiKeyMutation,
  useGetUserStrategiesQuery,
  useGetStrategyByIdQuery,
  useCreateStrategyMutation,
  useUpdateStrategyMutation,
  useDeleteStrategyMutation,
  useGetStopLossTypesQuery,
  useGetMLStrategiesQuery,
} = usersApi;