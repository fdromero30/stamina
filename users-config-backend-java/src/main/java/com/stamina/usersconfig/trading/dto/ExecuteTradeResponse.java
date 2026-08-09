package com.stamina.usersconfig.trading.dto;

import java.util.Map;

/**
 * Response from the smart trade execution endpoint.
 * Contains the position details returned by eToro.
 */
public record ExecuteTradeResponse(
        String status,
        String message,
        Integer positionId,
        Map<String, Object> rawResponse
) {
    public static ExecuteTradeResponse success(String message, Integer positionId, Map<String, Object> rawResponse) {
        return new ExecuteTradeResponse("success", message, positionId, rawResponse);
    }

    public static ExecuteTradeResponse error(String message) {
        return new ExecuteTradeResponse("error", message, null, null);
    }
}