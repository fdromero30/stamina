package com.stamina.usersconfig.trading.dto;

import java.util.Map;

/**
 * Response from the smart trade execution endpoint.
 * Contains the position details returned by eToro and the environment
 * (demo vs real) the trade was executed against.
 */
public record ExecuteTradeResponse(
        String status,
        String message,
        Integer positionId,
        Map<String, Object> rawResponse,
        Boolean demo
) {
    public static ExecuteTradeResponse success(String message, Integer positionId, Map<String, Object> rawResponse) {
        return new ExecuteTradeResponse("success", message, positionId, rawResponse, null);
    }

    public static ExecuteTradeResponse success(String message, Integer positionId, Map<String, Object> rawResponse, boolean demo) {
        return new ExecuteTradeResponse("success", message, positionId, rawResponse, demo);
    }

    public static ExecuteTradeResponse error(String message) {
        return new ExecuteTradeResponse("error", message, null, null, null);
    }
}