package com.stamina.usersconfig.trading.dto;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import java.math.BigDecimal;

/**
 * Extended order request used by the deterministic Python engine.
 * Includes all trade parameters computed by the signal logic (SL, TP, leverage, etc.).
 */
public record ExecuteTradeRequest(
        @NotBlank String userId,

        @NotNull @Min(1) Integer instrumentId,

        @NotNull Boolean isBuy,

        @NotNull @Positive Double units,

        @NotNull @Min(1) Integer leverage,

        /** Stop-loss price level. If null, no SL is set. */
        BigDecimal stopLoss,

        /** Take-profit price level. If null, no TP is set. */
        BigDecimal takeProfit,

        /** When the trade reaches this risk:reward ratio, SL is moved to breakeven. */
        BigDecimal breakEvenTrigger,

        /** Order type: "market" (default) or "limit" (avoid slippage). */
        String orderType,

        /** Limit price (required when orderType == "limit"). */
        BigDecimal limitPrice
) {
}
