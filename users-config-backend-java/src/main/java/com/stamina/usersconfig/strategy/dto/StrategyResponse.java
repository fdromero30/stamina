package com.stamina.usersconfig.strategy.dto;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;

import java.math.BigDecimal;
import java.time.LocalTime;
import java.util.UUID;

public record StrategyResponse(
    UUID id,
    UUID userId,
    String userDisplayName,
    String name,
    String symbol,
    BigDecimal maxPositionSize,
    boolean enabled,

    // Risk Management
    BigDecimal maxDrawdown,
    BigDecimal maxRiskPerTrade,
    BigDecimal maxDailyLoss,
    Integer maxOpenPositions,

    // Trade Parameters
    UUID stopLossTypeId,
    String stopLossTypeCode,
    String stopLossTypeDisplayName,
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
    UUID mlStrategyId,
    String mlStrategyCode,
    String mlStrategyDisplayName
) {
    public static StrategyResponse fromEntity(StrategyConfig strategy) {
        return new StrategyResponse(
            strategy.getId(),
            strategy.getUser().getId(),
            strategy.getUser().getDisplayName(),
            strategy.getName(),
            strategy.getSymbol(),
            strategy.getMaxPositionSize(),
            strategy.isEnabled(),

            strategy.getMaxDrawdown(),
            strategy.getMaxRiskPerTrade(),
            strategy.getMaxDailyLoss(),
            strategy.getMaxOpenPositions(),

            strategy.getStopLossType() != null ? strategy.getStopLossType().getId() : null,
            strategy.getStopLossType() != null ? strategy.getStopLossType().getCode() : null,
            strategy.getStopLossType() != null ? strategy.getStopLossType().getDisplayName() : null,
            strategy.getStopLoss(),
            strategy.getTakeProfit(),
            strategy.getSpreadThreshold(),

            strategy.getTradingWindowStart(),
            strategy.getTradingWindowEnd(),
            strategy.getTrailingStopActivation(),
            strategy.getBreakEvenTrigger(),

            strategy.getHito1TriggerR(),
            strategy.getHito2TriggerR(),
            strategy.getHito2SlR(),
            strategy.getBreakevenSpreadMult(),
            strategy.getTrailingEnabled(),
            strategy.getTrailingAtrMult(),
            strategy.getMaxTpFarR(),
            strategy.getUseCandleHighLow(),
            strategy.getSlUpdateRetrySeconds(),
            strategy.getMinSlUpdateSpacingPips(),

            strategy.isUseML(),
            strategy.getMlStrategy() != null ? strategy.getMlStrategy().getId() : null,
            strategy.getMlStrategy() != null ? strategy.getMlStrategy().getCode() : null,
            strategy.getMlStrategy() != null ? strategy.getMlStrategy().getDisplayName() : null
        );
    }
}