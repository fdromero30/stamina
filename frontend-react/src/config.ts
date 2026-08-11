// Runtime config: lee de window.__STAMINA_CONFIG__ (generado por
// entrypoint.sh) con fallback a import.meta.env (dev / Vite).

declare global {
  interface Window {
    __STAMINA_CONFIG__?: {
      usersConfigApiUrl?: string;
      tradingCoreUrl?: string;
    };
  }
}

const winConfig = typeof window !== "undefined" ? window.__STAMINA_CONFIG__ : undefined;

export const usersConfigApiUrl =
  winConfig?.usersConfigApiUrl ||
  import.meta.env.VITE_USERS_CONFIG_API_URL ||
  "/api";

export const tradingCoreUrl =
  winConfig?.tradingCoreUrl ||
  import.meta.env.VITE_TRADING_CORE_URL ||
  "/trading-core";