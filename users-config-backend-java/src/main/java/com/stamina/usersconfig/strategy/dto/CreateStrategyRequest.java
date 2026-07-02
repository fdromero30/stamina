package com.stamina.usersconfig.strategy.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;

import java.math.BigDecimal;
import java.util.UUID;

public record CreateStrategyRequest(
    @NotNull UUID userId,
    @NotBlank String name,
    @NotBlank String symbol,
    @DecimalMin("0.01") BigDecimal maxPositionSize,
    boolean enabled
) {
}