package com.stamina.usersconfig.trading.controller;

import com.stamina.usersconfig.trading.client.EtoroClient;
import com.stamina.usersconfig.trading.config.EtoroConfig;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/etoro/portfolio")
public class EtoroPortfolioController {

    private final EtoroClient etoroClient;
    private final EtoroConfig etoroConfig;

    public EtoroPortfolioController(EtoroClient etoroClient, EtoroConfig etoroConfig) {
        this.etoroClient = etoroClient;
        this.etoroConfig = etoroConfig;
    }

    private boolean resolveDemo(Boolean demo) {
        return demo != null ? demo : etoroConfig.isDemoMode();
    }

    @GetMapping
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> portfolio(
            @RequestParam("userId") UUID userId,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            return etoroClient.getPortfolio(userId, resolveDemo(demo));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro portfolio failed: " + e.getMessage());
        }
    }

    /**
     * Return only OPEN positions (isSettled=false) from the eToro portfolio.
     * Used by the trading bot to reconcile its local open-positions state
     * with positions that exist in eToro (e.g. after a restart/crash).
     */
    @GetMapping("/positions")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> openPositions(
            @RequestParam("userId") UUID userId,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            boolean useDemo = resolveDemo(demo);
            Map<String, Object> portfolio = etoroClient.getPortfolio(userId, useDemo);

            @SuppressWarnings("unchecked")
            Map<String, Object> clientPortfolio =
                    (Map<String, Object>) portfolio.getOrDefault("clientPortfolio", portfolio);
            List<Map<String, Object>> positions = new java.util.ArrayList<>();

            Object rawPositions = clientPortfolio.get("positions");
            if (rawPositions instanceof List<?> rawList) {
                for (Object item : rawList) {
                    if (item instanceof Map<?, ?> posMap) {
                        @SuppressWarnings("unchecked")
                        Map<String, Object> pos = (Map<String, Object>) posMap;
                        // Only active positions matter for monitoring
                        if (Boolean.FALSE.equals(pos.get("isSettled"))) {
                            positions.add(pos);
                        }
                    }
                }
            }

            return Map.of(
                    "positions", positions,
                    "count", positions.size(),
                    "demo", useDemo
            );
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro open positions failed: " + e.getMessage());
        }
    }

    @GetMapping("/pnl")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> pnl(
            @RequestParam("userId") UUID userId,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            return etoroClient.getPnl(userId, resolveDemo(demo));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro P&L failed: " + e.getMessage());
        }
    }

    @GetMapping("/trade-history")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> tradeHistory(
            @RequestParam("userId") UUID userId,
            @RequestParam("minDate") String minDate,
            @RequestParam(value = "page", defaultValue = "1") int page,
            @RequestParam(value = "pageSize", defaultValue = "20") int pageSize) {
        try {
            return etoroClient.getTradeHistory(userId, minDate, page, pageSize);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro trade history failed: " + e.getMessage());
        }
    }
}