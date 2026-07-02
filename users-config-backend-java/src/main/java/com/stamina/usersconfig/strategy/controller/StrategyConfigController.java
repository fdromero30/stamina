package com.stamina.usersconfig.strategy.controller;

import com.stamina.usersconfig.strategy.dto.CreateStrategyRequest;
import com.stamina.usersconfig.strategy.dto.StrategyResponse;
import com.stamina.usersconfig.strategy.service.StrategyConfigService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/strategies")
public class StrategyConfigController {

    private final StrategyConfigService strategyService;

    public StrategyConfigController(StrategyConfigService strategyService) {
        this.strategyService = strategyService;
    }

    @GetMapping
    List<StrategyResponse> list() {
        return strategyService.listAll();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    StrategyResponse create(@Valid @RequestBody CreateStrategyRequest request) {
        return strategyService.create(request);
    }
}