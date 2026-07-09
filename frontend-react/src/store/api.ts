import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { ApiKeyRow, AppUser, CreateApiKeyRequest, CreateUserRequest, RevealedKeyResponse } from "../types";

const usersConfigApiUrl = import.meta.env.VITE_USERS_CONFIG_API_URL ?? "http://localhost:8080";

export const usersApi = createApi({
  reducerPath: "usersApi",
  baseQuery: fetchBaseQuery({ baseUrl: usersConfigApiUrl }),
  tagTypes: ["Users", "ApiKeys"],
  endpoints: (builder) => ({
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

    getApiKeys: builder.query<ApiKeyRow[], string>({
      query: (userId) => `/api-keys?userId=${userId}`,
      providesTags: ["ApiKeys"],
    }),

    createApiKey: builder.mutation<ApiKeyRow, CreateApiKeyRequest>({
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
  }),
});

export const {
  useGetUsersQuery,
  useCreateUserMutation,
  useGetApiKeysQuery,
  useCreateApiKeyMutation,
  useRevealApiKeyMutation,
  useDeleteApiKeyMutation,
} = usersApi;
