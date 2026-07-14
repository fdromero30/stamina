package com.stamina.usersconfig.strategy.service;

import com.stamina.usersconfig.strategy.dto.CreateStrategyRequest;
import java.math.BigDecimal;
import com.stamina.usersconfig.strategy.dto.MLStrategyResponse;
import com.stamina.usersconfig.strategy.dto.StopLossTypeResponse;
import com.stamina.usersconfig.strategy.dto.StrategyResponse;
import com.stamina.usersconfig.strategy.dto.UpdateStrategyRequest;
import com.stamina.usersconfig.strategy.entity.MLStrategy;
import com.stamina.usersconfig.strategy.entity.StopLossType;
import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import com.stamina.usersconfig.strategy.repository.MLStrategyRepository;
import com.stamina.usersconfig.strategy.repository.StopLossTypeRepository;
import com.stamina.usersconfig.strategy.repository.StrategyConfigRepository;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;
import java.util.UUID;

@Service
public class StrategyConfigService {

    private final StrategyConfigRepository strategyRepository;
    private final AppUserRepository userRepository;
    private final StopLossTypeRepository stopLossTypeRepository;
    private final MLStrategyRepository mlStrategyRepository;

    public StrategyConfigService(StrategyConfigRepository strategyRepository,
                                  AppUserRepository userRepository,
                                  StopLossTypeRepository stopLossTypeRepository,
                                  MLStrategyRepository mlStrategyRepository) {
        this.strategyRepository = strategyRepository;
        this.userRepository = userRepository;
        this.stopLossTypeRepository = stopLossTypeRepository;
        this.mlStrategyRepository = mlStrategyRepository;
    }

    public List<StrategyResponse> listAll() {
        return strategyRepository.findAll()
            .stream()
            .map(StrategyResponse::fromEntity)
            .toList();
    }

    public List<StrategyResponse> listByUserId(UUID userId) {
        return strategyRepository.findByUserId(userId)
            .stream()
            .map(StrategyResponse::fromEntity)
            .toList();
    }

    @Transactional
    public StrategyResponse create(CreateStrategyRequest request) {
        AppUser user = userRepository.findById(request.userId())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        StrategyConfig strategy = new StrategyConfig(
            user,
            request.name(),
            request.symbol(),
            request.maxPositionSize(),
            request.enabled()
        );

        applyOptionalFields(strategy, request.maxDrawdown(), request.maxRiskPerTrade(),
            request.maxDailyLoss(), request.maxOpenPositions(), request.stopLossTypeId(),
            request.stopLoss(), request.takeProfit(), request.spreadThreshold(),
            request.tradingWindowStart(), request.tradingWindowEnd(),
            request.trailingStopActivation(), request.breakEvenTrigger(),
            request.useML(), request.mlStrategyId());

        StrategyConfig saved = strategyRepository.save(strategy);
        return StrategyResponse.fromEntity(saved);
    }

    @Transactional
    public StrategyResponse update(UUID id, UpdateStrategyRequest request) {
        StrategyConfig strategy = strategyRepository.findById(id)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Strategy not found"));

        if (request.name() != null) strategy.setName(request.name());
        if (request.symbol() != null) strategy.setSymbol(request.symbol());
        if (request.maxPositionSize() != null) strategy.setMaxPositionSize(request.maxPositionSize());
        if (request.enabled() != null) strategy.setEnabled(request.enabled());

        applyOptionalFields(strategy, request.maxDrawdown(), request.maxRiskPerTrade(),
            request.maxDailyLoss(), request.maxOpenPositions(), request.stopLossTypeId(),
            request.stopLoss(), request.takeProfit(), request.spreadThreshold(),
            request.tradingWindowStart(), request.tradingWindowEnd(),
            request.trailingStopActivation(), request.breakEvenTrigger(),
            request.useML(), request.mlStrategyId());

        StrategyConfig saved = strategyRepository.save(strategy);
        return StrategyResponse.fromEntity(saved);
    }

    @Transactional
    public void delete(UUID id) {
        if (!strategyRepository.existsById(id)) {
            throw new ResponseStatusException(HttpStatus.NOT_FOUND, "Strategy not found");
        }
        strategyRepository.deleteById(id);
    }

    public List<StopLossTypeResponse> listStopLossTypes() {
        return stopLossTypeRepository.findAll()
            .stream()
            .map(StopLossTypeResponse::fromEntity)
            .toList();
    }

    public List<MLStrategyResponse> listMLStrategies() {
        return mlStrategyRepository.findAll()
            .stream()
            .map(MLStrategyResponse::fromEntity)
            .toList();
    }

    private void applyOptionalFields(StrategyConfig strategy,
                                      BigDecimal maxDrawdown,
                                      BigDecimal maxRiskPerTrade,
                                      BigDecimal maxDailyLoss,
                                      Integer maxOpenPositions,
                                      UUID stopLossTypeId,
                                      BigDecimal stopLoss,
                                      BigDecimal takeProfit,
                                      BigDecimal spreadThreshold,
                                      java.time.LocalTime tradingWindowStart,
                                      java.time.LocalTime tradingWindowEnd,
                                      BigDecimal trailingStopActivation,
                                      BigDecimal breakEvenTrigger,
                                      Boolean useML,
                                      UUID mlStrategyId) {
        strategy.setMaxDrawdown(maxDrawdown);
        strategy.setMaxRiskPerTrade(maxRiskPerTrade);
        strategy.setMaxDailyLoss(maxDailyLoss);
        strategy.setMaxOpenPositions(maxOpenPositions);

        if (stopLossTypeId != null) {
            StopLossType slType = stopLossTypeRepository.findById(stopLossTypeId)
                .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "StopLossType not found"));
            strategy.setStopLossType(slType);
        } else {
            strategy.setStopLossType(null);
        }

        strategy.setStopLoss(stopLoss);
        strategy.setTakeProfit(takeProfit);
        strategy.setSpreadThreshold(spreadThreshold);
        strategy.setTradingWindowStart(tradingWindowStart);
        strategy.setTradingWindowEnd(tradingWindowEnd);
        strategy.setTrailingStopActivation(trailingStopActivation);
        strategy.setBreakEvenTrigger(breakEvenTrigger);

        if (useML != null) {
            strategy.setUseML(useML);
            if (useML && mlStrategyId != null) {
                MLStrategy ml = mlStrategyRepository.findById(mlStrategyId)
                    .orElseThrow(() -> new ResponseStatusException(HttpStatus.BAD_REQUEST, "MLStrategy not found"));
                strategy.setMlStrategy(ml);
            } else {
                strategy.setMlStrategy(null);
            }
        }
    }
}