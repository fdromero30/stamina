import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { AppUser, CreateUserRequest } from "../types";

const usersConfigApiUrl = import.meta.env.VITE_USERS_CONFIG_API_URL ?? "http://localhost:8080";

export const usersApi = createApi({
  reducerPath: "usersApi",
  baseQuery: fetchBaseQuery({ baseUrl: usersConfigApiUrl }),
  tagTypes: ["Users"],
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
  }),
});

export const { useGetUsersQuery, useCreateUserMutation } = usersApi;