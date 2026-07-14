import { describe, it, expect } from "vitest";
import type {
  StrategyConfig,
  CreateStrategyRequest,
  UpdateStrategyRequest,
  StopLossType,
  MLStrategy,
} from "../types";

describe("types", () => {
  it("StrategyConfig type is valid", () => {
    const config: StrategyConfig = {
      id: "abc-123",
      userId: "user-1",
      userDisplayName: "Test User",
      name: "Test Strat",
      symbol: "BTCUSDT",
      maxPositionSize: 0.5,
      enabled: true,
      maxDrawdown: null,
      maxRiskPerTrade: null,
      maxDailyLoss: null,
      maxOpenPositions: null,
      stopLossTypeId: null,
      stopLossTypeCode: null,
      stopLossTypeDisplayName: null,
      stopLoss: null,
      takeProfit: null,
      spreadThreshold: null,
      tradingWindowStart: null,
      tradingWindowEnd: null,
      trailingStopActivation: null,
      breakEvenTrigger: null,
      useML: false,
      mlStrategyId: null,
      mlStrategyCode: null,
      mlStrategyDisplayName: null,
    };
    expect(config.name).toBe("Test Strat");
    expect(config.useML).toBe(false);
  });

  it("StrategyConfig with all fields populated", () => {
    const config: StrategyConfig = {
      id: "abc",
      userId: "u1",
      userDisplayName: "User",
      name: "Full",
      symbol: "ETHUSDT",
      maxPositionSize: 1.0,
      enabled: true,
      maxDrawdown: 15.0,
      maxRiskPerTrade: 2.5,
      maxDailyLoss: 5.0,
      maxOpenPositions: 5,
      stopLossTypeId: "sl-1",
      stopLossTypeCode: "trailing",
      stopLossTypeDisplayName: "Trailing",
      stopLoss: 2.0,
      takeProfit: 4.0,
      spreadThreshold: 0.0005,
      tradingWindowStart: "08:00:00",
      tradingWindowEnd: "18:00:00",
      trailingStopActivation: 3.0,
      breakEvenTrigger: 1.5,
      useML: true,
      mlStrategyId: "ml-1",
      mlStrategyCode: "lstm",
      mlStrategyDisplayName: "LSTM",
    };
    expect(config.maxDrawdown).toBe(15.0);
    expect(config.useML).toBe(true);
    expect(config.mlStrategyCode).toBe("lstm");
  });

  it("CreateStrategyRequest type is valid", () => {
    const req: CreateStrategyRequest = {
      userId: "u1",
      name: "Test",
      symbol: "BTCUSDT",
      maxPositionSize: 0.5,
      enabled: true,
      maxDrawdown: 10.0,
      stopLossTypeId: "sl-1",
    };
    expect(req.name).toBe("Test");
    expect(req.maxDrawdown).toBe(10.0);
  });

  it("UpdateStrategyRequest type allows partial updates", () => {
    const req: UpdateStrategyRequest = {
      enabled: true,
      maxDrawdown: 20.0,
    };
    expect(req.enabled).toBe(true);
    expect(req.name).toBeUndefined();
  });

  it("StopLossType type is valid", () => {
    const sl: StopLossType = {
      id: "sl-1",
      code: "fixed_pct",
      displayName: "Fixed %",
      description: "A fixed percentage stop loss",
    };
    expect(sl.code).toBe("fixed_pct");
  });

  it("MLStrategy type is valid", () => {
    const ml: MLStrategy = {
      id: "ml-1",
      code: "xgboost",
      displayName: "XGBoost",
      description: "Gradient boosting model",
    };
    expect(ml.code).toBe("xgboost");
  });
});