package com.stamina.usersconfig.trading.controller;

import com.stamina.usersconfig.trading.client.EtoroClient;
import com.stamina.usersconfig.trading.config.EtoroConfig;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.util.Map;
import java.util.UUID;

/**
 * eToro trading proxy.
 *
 * Demo vs real is NOT a separate URL — both environments share the same
 * endpoints and the caller selects the mode with the {@code demo} query
 * parameter (defaults to {@code etoro.demo-mode} / {@code ETORO_DEMO}).
 * Demo execution simply routes to eToro's upstream /demo/ paths internally.
 */
@RestController
@RequestMapping("/etoro/trading")
public class EtoroTradingController {

    private final EtoroClient etoroClient;
    private final EtoroConfig etoroConfig;

    public EtoroTradingController(EtoroClient etoroClient, EtoroConfig etoroConfig) {
        this.etoroClient = etoroClient;
        this.etoroConfig = etoroConfig;
    }

    private boolean resolveDemo(Boolean demo) {
        return demo != null ? demo : etoroConfig.isDemoMode();
    }

    // ── Market orders ──────────────────────────────

    @PostMapping("/open-by-amount")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> openByAmount(
            @RequestParam("userId") UUID userId,
            @RequestParam("instrumentId") int instrumentId,
            @RequestParam("isBuy") boolean isBuy,
            @RequestParam(value = "leverage", defaultValue = "1") int leverage,
            @RequestParam("amount") double amount,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            return etoroClient.placeMarketOrderByAmount(
                    userId, instrumentId, isBuy, leverage, amount, resolveDemo(demo));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro open by amount failed: " + e.getMessage());
        }
    }

    @PostMapping("/open-by-units")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> openByUnits(
            @RequestParam("userId") UUID userId,
            @RequestParam("instrumentId") int instrumentId,
            @RequestParam("isBuy") boolean isBuy,
            @RequestParam(value = "leverage", defaultValue = "1") int leverage,
            @RequestParam("units") double units,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            return etoroClient.placeMarketOrderByUnits(
                    userId, instrumentId, isBuy, leverage, units, resolveDemo(demo));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro open by units failed: " + e.getMessage());
        }
    }

    @PostMapping("/close-position/{positionId}")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> closePosition(
            @RequestParam("userId") UUID userId,
            @PathVariable("positionId") int positionId,
            @RequestParam(value = "unitsToDeduct", required = false) Double unitsToDeduct,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            return etoroClient.closePosition(
                    userId, positionId, unitsToDeduct, resolveDemo(demo));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro close position failed: " + e.getMessage());
        }
    }

    @DeleteMapping("/cancel-order/{orderId}")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> cancelOrder(
            @RequestParam("userId") UUID userId,
            @PathVariable("orderId") int orderId,
            @RequestParam(value = "demo", required = false) Boolean demo) {
        try {
            return etoroClient.cancelOpenOrder(userId, orderId, resolveDemo(demo));
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro cancel order failed: " + e.getMessage());
        }
    }

    // ── Stop Loss / Take Profit updates ──────────

    @PutMapping("/stop-loss/{positionId}")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> updateStopLoss(
            @RequestParam("userId") UUID userId,
            @PathVariable("positionId") int positionId,
            @RequestParam(value = "demo", required = false) Boolean demo,
            @RequestBody Map<String, Object> body) {
        try {
            Object slValue = body.get("stopLoss") != null ? body.get("stopLoss") : body.get("StopLossRate");
            if (slValue == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Missing required field: stopLoss");
            }
            java.math.BigDecimal stopLoss = new java.math.BigDecimal(slValue.toString());
            return etoroClient.updateStopLoss(userId, positionId, stopLoss, resolveDemo(demo));
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro update stop loss failed: " + e.getMessage());
        }
    }

    @PutMapping("/take-profit/{positionId}")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> updateTakeProfit(
            @RequestParam("userId") UUID userId,
            @PathVariable("positionId") int positionId,
            @RequestParam(value = "demo", required = false) Boolean demo,
            @RequestBody Map<String, Object> body) {
        try {
            Object tpValue = body.get("takeProfit") != null ? body.get("takeProfit") : body.get("TakeProfitRate");
            if (tpValue == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Missing required field: takeProfit");
            }
            java.math.BigDecimal takeProfit = new java.math.BigDecimal(tpValue.toString());
            return etoroClient.setTakeProfit(userId, positionId, takeProfit, resolveDemo(demo));
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro update take profit failed: " + e.getMessage());
        }
    }
}