import { configureStore } from "@reduxjs/toolkit";
import { usersApi } from "./api";
import { etoroApi } from "./etoroApi";
import { botApi } from "./botApi";
import botStateReducer from "./botStateSlice";

export const store = configureStore({
  reducer: {
    [usersApi.reducerPath]: usersApi.reducer,
    [etoroApi.reducerPath]: etoroApi.reducer,
    [botApi.reducerPath]: botApi.reducer,
    botState: botStateReducer,
  },
  middleware: (getDefaultMiddleware) =>
    getDefaultMiddleware().concat(usersApi.middleware, etoroApi.middleware, botApi.middleware),
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;