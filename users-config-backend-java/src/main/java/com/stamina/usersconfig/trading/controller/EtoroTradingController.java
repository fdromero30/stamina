package com.stamina.usersconfig.trading.controller;

import com.stamina.usersconfig.trading.client.EtoroClient;
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

@RestController
@RequestMapping("/etoro/trading")
public class EtoroTradingController {

    private final EtoroClient etoroClient;

    public EtoroTradingController(EtoroClient etoroClient) {
        this.etoroClient = etoroClient;
    }

    // ── Demo ────────────────────────────────────

    @PostMapping("/demo/open-by-amount")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> demoOpenByAmount(
            @RequestParam("userId") UUID userId,
            @RequestParam("instrumentId") int instrumentId,
            @RequestParam("isBuy") boolean isBuy,
            @RequestParam(value = "leverage", defaultValue = "1") int leverage,
            @RequestParam("amount") double amount) {
        try {
            return etoroClient.placeDemoMarketOrderByAmount(userId, instrumentId, isBuy, leverage, amount);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro demo open by amount failed: " + e.getMessage());
        }
    }

    @PostMapping("/demo/open-by-units")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> demoOpenByUnits(
            @RequestParam("userId") UUID userId,
            @RequestParam("instrumentId") int instrumentId,
            @RequestParam("isBuy") boolean isBuy,
            @RequestParam(value = "leverage", defaultValue = "1") int leverage,
            @RequestParam("units") double units) {
        try {
            return etoroClient.placeDemoMarketOrderByUnits(userId, instrumentId, isBuy, leverage, units);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro demo open by units failed: " + e.getMessage());
        }
    }

    @PostMapping("/demo/close-position/{positionId}")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> demoClosePosition(
            @RequestParam("userId") UUID userId,
            @PathVariable("positionId") int positionId,
            @RequestParam(value = "unitsToDeduct", required = false) Double unitsToDeduct) {
        try {
            return etoroClient.closeDemoPosition(userId, positionId, unitsToDeduct);
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro demo close position failed: " + e.getMessage());
        }
    }

    // ── Real ────────────────────────────────────

    @PostMapping("/open-by-amount")
    @ResponseStatus(HttpStatus.OK)
    public Map<String, Object> openByAmount(
            @RequestParam("userId") UUID userId,
            @RequestParam("instrumentId") int instrumentId,
            @RequestParam("isBuy") boolean isBuy,
            @RequestParam(value = "leverage", defaultValue = "1") int leverage,
            @RequestParam("amount") double amount) {
        try {
            return etoroClient.placeMarketOrderByAmount(userId, instrumentId, isBuy, leverage, amount);
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
            @RequestParam("units") double units) {
        try {
            return etoroClient.placeMarketOrderByUnits(userId, instrumentId, isBuy, leverage, units);
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
            @RequestParam(value = "unitsToDeduct", required = false) Double unitsToDeduct) {
        try {
            return etoroClient.closePosition(userId, positionId, unitsToDeduct);
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
            @RequestParam(value = "demo", defaultValue = "false") boolean demo) {
        try {
            return etoroClient.cancelOpenOrder(userId, orderId, demo);
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
            @RequestBody Map<String, Object> body) {
        try {
            Object slValue = body.get("stopLoss") != null ? body.get("stopLoss") : body.get("StopLossRate");
            if (slValue == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Missing required field: stopLoss");
            }
            java.math.BigDecimal stopLoss = new java.math.BigDecimal(slValue.toString());
            return etoroClient.updateStopLoss(userId, positionId, stopLoss);
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
            @RequestBody Map<String, Object> body) {
        try {
            Object tpValue = body.get("takeProfit") != null ? body.get("takeProfit") : body.get("TakeProfitRate");
            if (tpValue == null) {
                throw new ResponseStatusException(HttpStatus.BAD_REQUEST,
                        "Missing required field: takeProfit");
            }
            java.math.BigDecimal takeProfit = new java.math.BigDecimal(tpValue.toString());
            return etoroClient.setTakeProfit(userId, positionId, takeProfit);
        } catch (ResponseStatusException e) {
            throw e;
        } catch (Exception e) {
            throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR,
                    "eToro update take profit failed: " + e.getMessage());
        }
    }
}