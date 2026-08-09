package com.stamina.usersconfig.trading.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record ExecuteOrderRequest(
        @NotBlank String userId,
        @NotBlank String symbol,
        @NotBlank @Pattern(regexp = "^(buy|sell)$") String side,
        @Min(1) double units
) {
}