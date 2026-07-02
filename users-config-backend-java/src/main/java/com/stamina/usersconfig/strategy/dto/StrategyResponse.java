package com.stamina.usersconfig.strategy.dto;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;

import java.math.BigDecimal;
import java.util.UUID;

public record StrategyResponse(
    UUID id,
    UUID userId,
    String userDisplayName,
    String name,
    String symbol,
    BigDecimal maxPositionSize,
    boolean enabled
) {
    public static StrategyResponse fromEntity(StrategyConfig strategy) {
        return new StrategyResponse(
            strategy.getId(),
            strategy.getUser().getId(),
            strategy.getUser().getDisplayName(),
            strategy.getName(),
            strategy.getSymbol(),
            strategy.getMaxPositionSize(),
            strategy.isEnabled()
        );
    }
}