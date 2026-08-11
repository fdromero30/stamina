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

    /** Estrategia por defecto de la app, asignada automáticamente cuando un usuario no tiene ninguna. */
    public static final String DEFAULT_STRATEGY_NAME = "MA200 + MA9 Crossover (Default)";
    public static final String DEFAULT_STRATEGY_SYMBOL = "EUR/USD";
    public static final BigDecimal DEFAULT_MAX_POSITION_SIZE = new BigDecimal("0.10");
    public static final BigDecimal DEFAULT_MAX_RISK_PER_TRADE = new BigDecimal("0.005"); // 0.5%
    public static final Integer DEFAULT_MAX_OPEN_POSITIONS = 2;
    public static final BigDecimal DEFAULT_BREAK_EVEN_TRIGGER = new BigDecimal("1.5");

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

    @Transactional(readOnly = true)
    public List<StrategyResponse> listAll() {
        return strategyRepository.findAll()
            .stream()
            .map(StrategyResponse::fromEntity)
            .toList();
    }

    @Transactional
    public List<StrategyResponse> listByUserId(UUID userId) {
        List<StrategyConfig> strategies = strategyRepository.findByUserId(userId);
        if (strategies.isEmpty()) {
            ensureDefaultStrategy(userId);
            strategies = strategyRepository.findByUserId(userId);
        }
        return strategies.stream()
            .map(StrategyResponse::fromEntity)
            .toList();
    }

    /**
     * Asegura que el usuario tenga al menos la estrategia por defecto de la app.
     * Si el usuario ya tiene estrategias las respeta; si no tiene ninguna, crea
     * y persiste una {@link StrategyConfig} default habilitada.
     */
    @Transactional
    public void ensureDefaultStrategy(UUID userId) {
        if (!strategyRepository.findByUserId(userId).isEmpty()) {
            return;
        }

        AppUser user = userRepository.findById(userId)
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        StrategyConfig defaultStrategy = new StrategyConfig(
            user,
            DEFAULT_STRATEGY_NAME,
            DEFAULT_STRATEGY_SYMBOL,
            DEFAULT_MAX_POSITION_SIZE,
            true // enabled
        );
        defaultStrategy.setMaxOpenPositions(DEFAULT_MAX_OPEN_POSITIONS);
        defaultStrategy.setMaxRiskPerTrade(DEFAULT_MAX_RISK_PER_TRADE);
        defaultStrategy.setBreakEvenTrigger(DEFAULT_BREAK_EVEN_TRIGGER);

        strategyRepository.save(defaultStrategy);
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