export type AuthMode = "login" | "signup";

export type Session = {
  id: string;
  name: string;
  email: string;
};

export type StrategyRow = {
  name: string;
  status: string;
  risk: string;
  pnl: string;
};

/* -------- API types (Users Config backend) -------- */

export type AppUser = {
  id: string;
  email: string;
  displayName: string;
  createdAt: string;
};

export type CreateUserRequest = {
  email: string;
  displayName: string;
  password: string;
};

export type LoginRequest = {
  email: string;
  password: string;
};

/* -------- API Key types -------- */

export type ApiKeyRow = {
  id: string;
  label: string;
  broker: string;
  maskedKey: string;
  createdAt: string;
};

export type CreateApiKeyRequest = {
  userId: string;
  label: string;
  broker: string;
  publicKey: string;
  privateKey: string;
};

export type RevealedKeyResponse = {
  apiKey: string;
};

/* -------- Strategy Config types -------- */

export type StopLossType = {
  id: string;
  code: string;
  displayName: string;
  description: string;
};

export type MLStrategy = {
  id: string;
  code: string;
  displayName: string;
  description: string;
};

export type StrategyConfig = {
  id: string;
  userId: string;
  userDisplayName: string;
  name: string;
  symbol: string;
  maxPositionSize: number;
  enabled: boolean;

  // Risk Management
  maxDrawdown: number | null;
  maxRiskPerTrade: number | null;
  maxDailyLoss: number | null;
  maxOpenPositions: number | null;

  // Trade Parameters
  stopLossTypeId: string | null;
  stopLossTypeCode: string | null;
  stopLossTypeDisplayName: string | null;
  stopLoss: number | null;
  takeProfit: number | null;
  spreadThreshold: number | null;

  // Time & Execution
  tradingWindowStart: string | null;
  tradingWindowEnd: string | null;
  trailingStopActivation: number | null;
  breakEvenTrigger: number | null;

  // ML
  useML: boolean;
  mlStrategyId: string | null;
  mlStrategyCode: string | null;
  mlStrategyDisplayName: string | null;
};

export type CreateStrategyRequest = {
  userId: string;
  name: string;
  symbol: string;
  maxPositionSize: number;
  enabled: boolean;
  maxDrawdown?: number | null;
  maxRiskPerTrade?: number | null;
  maxDailyLoss?: number | null;
  maxOpenPositions?: number | null;
  stopLossTypeId?: string | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
  spreadThreshold?: number | null;
  tradingWindowStart?: string | null;
  tradingWindowEnd?: string | null;
  trailingStopActivation?: number | null;
  breakEvenTrigger?: number | null;
  useML?: boolean;
  mlStrategyId?: string | null;
};

export type UpdateStrategyRequest = {
  name?: string;
  symbol?: string;
  maxPositionSize?: number;
  enabled?: boolean;
  maxDrawdown?: number | null;
  maxRiskPerTrade?: number | null;
  maxDailyLoss?: number | null;
  maxOpenPositions?: number | null;
  stopLossTypeId?: string | null;
  stopLoss?: number | null;
  takeProfit?: number | null;
  spreadThreshold?: number | null;
  tradingWindowStart?: string | null;
  tradingWindowEnd?: string | null;
  trailingStopActivation?: number | null;
  breakEvenTrigger?: number | null;
  useML?: boolean;
  mlStrategyId?: string | null;
};