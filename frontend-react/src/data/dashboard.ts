import type { StrategyRow } from "../types";
import { tradingCoreUrl, usersConfigApiUrl } from "../config";

export { tradingCoreUrl };
export const usersConfigUrl = usersConfigApiUrl;

export const strategyRows: StrategyRow[] = [
  { name: "Momentum BTC", status: "Paper", risk: "2.1%", pnl: "+4.8%" },
  { name: "ETH Mean Reversion", status: "Review", risk: "1.4%", pnl: "+1.2%" },
  { name: "Index Hedge", status: "Live guard", risk: "0.8%", pnl: "-0.3%" },
];
