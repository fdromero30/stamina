import { configureStore } from "@reduxjs/toolkit";
import { usersApi } from "./api";
import { etoroApi } from "./etoroApi";

export const store = configureStore({
  reducer: {
    [usersApi.reducerPath]: usersApi.reducer,
    [etoroApi.reducerPath]: etoroApi.reducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(usersApi.middleware, etoroApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;