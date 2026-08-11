package com.stamina.usersconfig.trading.service;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import com.stamina.usersconfig.strategy.repository.StrategyConfigRepository;
import com.stamina.usersconfig.trading.client.EtoroClient;
import com.stamina.usersconfig.trading.dto.ExecuteOrderRequest;
import com.stamina.usersconfig.trading.dto.ExecuteOrderResponse;
import com.stamina.usersconfig.trading.dto.ExecuteTradeRequest;
import com.stamina.usersconfig.trading.dto.ExecuteTradeResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Service
public class TradingService {

    private final StrategyConfigRepository strategyRepository;
    private final EtoroClient etoroClient;

    public TradingService(StrategyConfigRepository strategyRepository, EtoroClient etoroClient) {
        this.strategyRepository = strategyRepository;
        this.etoroClient = etoroClient;
    }

    public ExecuteOrderResponse execute(ExecuteOrderRequest request) {
        UUID userId = UUID.fromString(request.userId());

        List<StrategyConfig> strategies = strategyRepository.findBySymbolAndEnabledTrue(request.symbol());

        if (strategies.isEmpty()) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "No enabled strategy found for symbol: " + request.symbol()
            );
        }

        BigDecimal maxPosition = strategies.stream()
                .map(StrategyConfig::getMaxPositionSize)
                .max(BigDecimal::compareTo)
                .orElse(BigDecimal.ZERO);

        if (BigDecimal.valueOf(request.units()).compareTo(maxPosition) > 0) {
            throw new ResponseStatusException(
                    HttpStatus.BAD_REQUEST,
                    "Requested units " + request.units() + " exceed max position size " + maxPosition + " for symbol: " + request.symbol()
            );
        }

        try {
            etoroClient.placeOrder(userId, request.symbol(), request.side(), request.units());
            return ExecuteOrderResponse.success("Order placed for " + request.units() + " units of " + request.symbol());
        } catch (Exception e) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to place order on eToro: " + e.getMessage()
            );
        }
    }

    /**
     * Smart trade execution used by the deterministic Python engine.
     * Opens a position (market or limit) on eToro and optionally sets SL/TP.
     */
    public ExecuteTradeResponse executeSmart(ExecuteTradeRequest request) {
        UUID userId = UUID.fromString(request.userId());

        try {
            Map<String, Object> openResult;
            Integer positionId;

            String orderType = request.orderType() == null ? "market" : request.orderType();
            boolean isLimit = "limit".equalsIgnoreCase(orderType);

            if (isLimit) {
                // ── Limit order: place the order at the exact triggered price
                //    (avoids slippage). eToro places SL/TP directly on the order.
                if (request.limitPrice() == null) {
                    return ExecuteTradeResponse.error(
                            "Limit order requested but limitPrice is null"
                    );
                }
                openResult = etoroClient.placeLimitOrderByUnits(
                        userId,
                        request.instrumentId(),
                        request.isBuy(),
                        request.leverage(),
                        request.units(),
                        request.limitPrice(),
                        request.stopLoss(),
                        request.takeProfit()
                );

                // Extract the OPEN ORDER id (limit orders are pending until filled)
                positionId = extractPositionId(openResult);
                if (positionId == null) {
                    // Some eToro limit-order responses expose the ID as orderId
                    Integer orderId = extractOrderId(openResult);
                    if (orderId == null) {
                        return ExecuteTradeResponse.error(
                                "Limit order placed but could not extract order ID from eToro response"
                        );
                    }
                    positionId = orderId;
                }

                String side = request.isBuy() ? "buy" : "sell";
                return ExecuteTradeResponse.success(
                        side + " LIMIT " + request.units() + " units of instrument "
                                + request.instrumentId() + " at limit " + request.limitPrice()
                                + " (order " + positionId + ")",
                        positionId,
                        openResult
                );
            }

            // ── Market order: open the position on eToro
            openResult = etoroClient.placeMarketOrderByUnits(
                    userId,
                    request.instrumentId(),
                    request.isBuy(),
                    request.leverage(),
                    request.units()
            );

            // Extract position ID from the response
            positionId = extractPositionId(openResult);
            if (positionId == null) {
                return ExecuteTradeResponse.error(
                        "Position opened but could not extract position ID from eToro response"
                );
            }

            // 2. Set stop loss if provided
            if (request.stopLoss() != null) {
                try {
                    etoroClient.setStopLoss(userId, positionId, request.stopLoss());
                } catch (Exception e) {
                    return ExecuteTradeResponse.error(
                            "Position " + positionId + " opened but failed to set stop loss: " + e.getMessage()
                    );
                }
            }

            // 3. Set take profit if provided
            if (request.takeProfit() != null) {
                try {
                    etoroClient.setTakeProfit(userId, positionId, request.takeProfit());
                } catch (Exception e) {
                    return ExecuteTradeResponse.error(
                            "Position " + positionId + " opened but failed to set take profit: " + e.getMessage()
                    );
                }
            }

            String side = request.isBuy() ? "buy" : "sell";
            return ExecuteTradeResponse.success(
                    side + " " + request.units() + " units of instrument " + request.instrumentId()
                            + " at position " + positionId,
                    positionId,
                    openResult
            );

        } catch (Exception e) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to execute smart trade: " + e.getMessage()
            );
        }
    }

    /**
     * Updates the stop loss on an existing position (e.g., for breakeven adjustments).
     */
    public void updatePositionStopLoss(UUID userId, int positionId, BigDecimal newStopLoss) {
        try {
            etoroClient.updateStopLoss(userId, positionId, newStopLoss);
        } catch (Exception e) {
            throw new ResponseStatusException(
                    HttpStatus.INTERNAL_SERVER_ERROR,
                    "Failed to update stop loss for position " + positionId + ": " + e.getMessage()
            );
        }
    }

    @SuppressWarnings("unchecked")
    private Integer extractPositionId(Map<String, Object> openResult) {
        // eToro typically returns position ID in the response
        // Try common keys: "PositionID", "positionId", "id"
        for (String key : List.of("PositionID", "positionId", "id")) {
            Object value = openResult.get(key);
            if (value instanceof Number number) {
                return number.intValue();
            }
        }
        return null;
    }

    @SuppressWarnings("unchecked")
    private Integer extractOrderId(Map<String, Object> openResult) {
        // Limit orders often return the open-order id under different keys
        for (String key : List.of("OrderID", "orderId", "OpenOrderID", "openOrderId")) {
            Object value = openResult.get(key);
            if (value instanceof Number number) {
                return number.intValue();
            }
        }
        return null;
    }
}
