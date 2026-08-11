package com.stamina.usersconfig.strategy.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.time.LocalTime;
import java.util.UUID;

public record CreateStrategyRequest(
    @NotNull UUID userId,
    @NotBlank String name,
    @NotBlank String symbol,
    @DecimalMin("0.01") BigDecimal maxPositionSize,
    boolean enabled,

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

    // Transversal Risk Management (máquina de estados + trailing ATR)
    BigDecimal hito1TriggerR,
    BigDecimal hito2TriggerR,
    BigDecimal hito2SlR,
    BigDecimal breakevenSpreadMult,
    Boolean trailingEnabled,
    BigDecimal trailingAtrMult,
    BigDecimal maxTpFarR,
    Boolean useCandleHighLow,
    Integer slUpdateRetrySeconds,
    BigDecimal minSlUpdateSpacingPips,

    // ML
    boolean useML,
    UUID mlStrategyId
) {
}