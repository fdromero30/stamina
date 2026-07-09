package com.stamina.usersconfig.trading.dto;

public record ExecuteOrderResponse(
        String status,
        String message
) {
    public static ExecuteOrderResponse success(String message) {
        return new ExecuteOrderResponse("success", message);
    }

    public static ExecuteOrderResponse error(String message) {
        return new ExecuteOrderResponse("error", message);
    }
}