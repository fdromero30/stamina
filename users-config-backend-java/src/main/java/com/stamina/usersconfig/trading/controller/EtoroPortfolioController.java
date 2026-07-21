package com.stamina.usersconfig.trading.controller;

import com.stamina.usersconfig.trading.client.EtoroClient;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/etoro/portfolio")
public class EtoroPortfolioController {

    private final EtoroClient etoroClient;

    public EtoroPortfolioController(EtoroClient etoroClient) {
        this.etoroClient = etoroClient;
    }

    @GetMapping
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> portfolio(@RequestParam("userId") UUID userId) {
        try {
            return etoroClient.getPortfolio(userId);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro portfolio failed: " + e.getMessage());
        }
    }

    @GetMapping("/demo")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> demoPortfolio(@RequestParam("userId") UUID userId) {
        try {
            return etoroClient.getDemoPortfolio(userId);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro demo portfolio failed: " + e.getMessage());
        }
    }

    @GetMapping("/pnl")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> realPnl(@RequestParam("userId") UUID userId) {
        try {
            return etoroClient.getRealPnl(userId);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro real P&L failed: " + e.getMessage());
        }
    }

    @GetMapping("/pnl/demo")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> demoPnl(@RequestParam("userId") UUID userId) {
        try {
            return etoroClient.getDemoPnl(userId);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro demo P&L failed: " + e.getMessage());
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