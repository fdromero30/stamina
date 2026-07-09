package com.stamina.usersconfig.trading.controller;

import com.stamina.usersconfig.trading.dto.ExecuteOrderRequest;
import com.stamina.usersconfig.trading.dto.ExecuteOrderResponse;
import com.stamina.usersconfig.trading.service.TradingService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/orders")
public class TradingController {

    private final TradingService tradingService;

    public TradingController(TradingService tradingService) {
        this.tradingService = tradingService;
    }

    @PostMapping("/execute")
    @ResponseStatus(HttpStatus.OK)
    public ExecuteOrderResponse execute(@Valid @RequestBody ExecuteOrderRequest request) {
        return tradingService.execute(request);
    }
}