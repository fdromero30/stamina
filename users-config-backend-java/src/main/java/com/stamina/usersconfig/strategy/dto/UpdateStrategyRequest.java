package com.stamina.usersconfig.strategy.dto;

import java.math.BigDecimal;
import java.time.LocalTime;
import java.util.UUID;

public record UpdateStrategyRequest(
    String name,
    String symbol,
    BigDecimal maxPositionSize,
    Boolean enabled,

    // Risk Management
    BigDecimal maxDrawdown,
    BigDecimal maxRiskPerTrade,
    BigDecimal maxDailyLoss,
    Integer maxOpenPositions,

    // Trade Parameters
    UUID stopLossTypeId,
    BigDecimal stopLoss,
    BigDecimal takeProfit,
    BigDecimal spreadThreshold,

    // Time & Execution
    LocalTime tradingWindowStart,
    LocalTime tradingWindowEnd,
    BigDecimal trailingStopActivation,
    BigDecimal breakEvenTrigger,

    // ML
    Boolean useML,
    UUID mlStrategyId
) {
}