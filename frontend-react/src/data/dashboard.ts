import type { StrategyRow } from "../types";

export const tradingCoreUrl = import.meta.env.VITE_TRADING_CORE_URL || "/trading-core";
export const usersConfigUrl = import.meta.env.VITE_USERS_CONFIG_API_URL || "/api";

export const strategyRows: StrategyRow[] = [
  { name: "Momentum BTC", status: "Paper", risk: "2.1%", pnl: "+4.8%" },
  { name: "ETH Mean Reversion", status: "Review", risk: "1.4%", pnl: "+1.2%" },
  { name: "Index Hedge", status: "Live guard", risk: "0.8%", pnl: "-0.3%" },
];
