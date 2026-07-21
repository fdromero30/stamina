package com.stamina.usersconfig.trading.service;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import com.stamina.usersconfig.strategy.repository.StrategyConfigRepository;
import com.stamina.usersconfig.trading.client.EtoroClient;
import com.stamina.usersconfig.trading.dto.ExecuteOrderRequest;
import com.stamina.usersconfig.trading.dto.ExecuteOrderResponse;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.util.List;
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
}