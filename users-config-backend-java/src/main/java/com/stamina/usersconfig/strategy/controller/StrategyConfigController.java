package com.stamina.usersconfig.strategy.controller;

import com.stamina.usersconfig.strategy.dto.CreateStrategyRequest;
import com.stamina.usersconfig.strategy.dto.MLStrategyResponse;
import com.stamina.usersconfig.strategy.dto.StopLossTypeResponse;
import com.stamina.usersconfig.strategy.dto.StrategyResponse;
import com.stamina.usersconfig.strategy.dto.UpdateStrategyRequest;
import com.stamina.usersconfig.strategy.service.StrategyConfigService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/strategies")
public class StrategyConfigController {

    private final StrategyConfigService strategyService;

    public StrategyConfigController(StrategyConfigService strategyService) {
        this.strategyService = strategyService;
    }

    @GetMapping
    List<StrategyResponse> list(@RequestParam(required = false) UUID userId) {
        if (userId != null) {
            return strategyService.listByUserId(userId);
        }
        return strategyService.listAll();
    }

    @GetMapping("/{id}")
    StrategyResponse getById(@PathVariable UUID id) {
        // For simplicity, we reuse listAll and filter. In production use a dedicated find.
        return strategyService.listAll().stream()
            .filter(s -> s.id().equals(id))
            .findFirst()
            .orElseThrow(() -> new org.springframework.web.server.ResponseStatusException(
                org.springframework.http.HttpStatus.NOT_FOUND, "Strategy not found"));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    StrategyResponse create(@Valid @RequestBody CreateStrategyRequest request) {
        return strategyService.create(request);
    }

    @PutMapping("/{id}")
    StrategyResponse update(@PathVariable UUID id, @Valid @RequestBody UpdateStrategyRequest request) {
        return strategyService.update(id, request);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void delete(@PathVariable UUID id) {
        strategyService.delete(id);
    }

    @GetMapping("/stop-loss-types")
    List<StopLossTypeResponse> listStopLossTypes() {
        return strategyService.listStopLossTypes();
    }

    @GetMapping("/ml-strategies")
    List<MLStrategyResponse> listMLStrategies() {
        return strategyService.listMLStrategies();
    }
}