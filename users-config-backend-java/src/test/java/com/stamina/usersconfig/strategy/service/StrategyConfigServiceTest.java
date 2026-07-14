package com.stamina.usersconfig.strategy.service;

import com.stamina.usersconfig.strategy.dto.CreateStrategyRequest;
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
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.time.LocalTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class StrategyConfigServiceTest {

    @Mock
    private StrategyConfigRepository strategyRepository;
    @Mock
    private AppUserRepository userRepository;
    @Mock
    private StopLossTypeRepository stopLossTypeRepository;
    @Mock
    private MLStrategyRepository mlStrategyRepository;

    private StrategyConfigService service;
    private AppUser testUser;
    private UUID userId;
    private StopLossType slType;
    private UUID slTypeId;

    @BeforeEach
    void setUp() {
        service = new StrategyConfigService(strategyRepository, userRepository, stopLossTypeRepository, mlStrategyRepository);
        userId = UUID.randomUUID();
        slTypeId = UUID.randomUUID();
        testUser = new AppUser("test@test.com", "Test User", "password");
        // Use reflection to set id since AppUser doesn't have a setId
        try {
            var idField = AppUser.class.getDeclaredField("id");
            idField.setAccessible(true);
            idField.set(testUser, userId);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        slType = new StopLossType("fixed_pct", "Fixed %", "A fixed percentage stop loss");
        try {
            var idField = StopLossType.class.getDeclaredField("id");
            idField.setAccessible(true);
            idField.set(slType, slTypeId);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
    }

    @Test
    void listAll_shouldReturnAllStrategies() {
        var strategy = new StrategyConfig(testUser, "Test Strat", "BTCUSDT", BigDecimal.ONE, true);
        when(strategyRepository.findAll()).thenReturn(List.of(strategy));

        List<StrategyResponse> result = service.listAll();

        assertThat(result).hasSize(1);
        assertThat(result.get(0).name()).isEqualTo("Test Strat");
        assertThat(result.get(0).symbol()).isEqualTo("BTCUSDT");
    }

    @Test
    void listByUserId_shouldReturnStrategiesForUser() {
        var strategy = new StrategyConfig(testUser, "User Strat", "ETHUSDT", BigDecimal.TEN, false);
        when(strategyRepository.findByUserId(userId)).thenReturn(List.of(strategy));

        List<StrategyResponse> result = service.listByUserId(userId);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).name()).isEqualTo("User Strat");
    }

    @Test
    void create_shouldSaveAndReturnStrategy() {
        var request = new CreateStrategyRequest(
            userId, "New Strat", "SOLUSDT", new BigDecimal("0.5"), true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            false, null
        );
        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));
        var saved = new StrategyConfig(testUser, "New Strat", "SOLUSDT", new BigDecimal("0.5"), true);
        when(strategyRepository.save(any())).thenReturn(saved);

        StrategyResponse result = service.create(request);

        assertThat(result.name()).isEqualTo("New Strat");
        assertThat(result.symbol()).isEqualTo("SOLUSDT");
        verify(strategyRepository).save(any());
    }

    @Test
    void create_shouldThrowWhenUserNotFound() {
        var request = new CreateStrategyRequest(
            userId, "X", "Y", BigDecimal.ONE, true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            false, null
        );
        when(userRepository.findById(userId)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.create(request))
            .isInstanceOf(ResponseStatusException.class)
            .hasMessageContaining("User not found");
    }

    @Test
    void create_shouldApplyOptionalFields() {
        UUID mlId = UUID.randomUUID();
        var mlStrategy = new MLStrategy("lstm", "LSTM", "Long Short-Term Memory");
        try {
            var idField = MLStrategy.class.getDeclaredField("id");
            idField.setAccessible(true);
            idField.set(mlStrategy, mlId);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        var request = new CreateStrategyRequest(
            userId, "ML Strat", "BTCUSDT", new BigDecimal("1.0"), true,
            new BigDecimal("10.0"), new BigDecimal("2.0"), new BigDecimal("5.0"), 3,
            slTypeId, new BigDecimal("1.5"), new BigDecimal("3.0"), new BigDecimal("0.001"),
            LocalTime.of(9, 30), LocalTime.of(16, 0), new BigDecimal("2.0"), new BigDecimal("1.0"),
            true, mlId
        );
        when(userRepository.findById(userId)).thenReturn(Optional.of(testUser));
        when(stopLossTypeRepository.findById(slTypeId)).thenReturn(Optional.of(slType));
        when(mlStrategyRepository.findById(mlId)).thenReturn(Optional.of(mlStrategy));
        var saved = new StrategyConfig(testUser, "ML Strat", "BTCUSDT", new BigDecimal("1.0"), true);
        saved.setMaxDrawdown(new BigDecimal("10.0"));
        saved.setMaxRiskPerTrade(new BigDecimal("2.0"));
        saved.setMaxDailyLoss(new BigDecimal("5.0"));
        saved.setMaxOpenPositions(3);
        saved.setStopLossType(slType);
        saved.setStopLoss(new BigDecimal("1.5"));
        saved.setTakeProfit(new BigDecimal("3.0"));
        saved.setSpreadThreshold(new BigDecimal("0.001"));
        saved.setTradingWindowStart(LocalTime.of(9, 30));
        saved.setTradingWindowEnd(LocalTime.of(16, 0));
        saved.setTrailingStopActivation(new BigDecimal("2.0"));
        saved.setBreakEvenTrigger(new BigDecimal("1.0"));
        saved.setUseML(true);
        saved.setMlStrategy(mlStrategy);
        when(strategyRepository.save(any())).thenReturn(saved);

        StrategyResponse result = service.create(request);

        assertThat(result.maxDrawdown()).isEqualByComparingTo(new BigDecimal("10.0"));
        assertThat(result.maxRiskPerTrade()).isEqualByComparingTo(new BigDecimal("2.0"));
        assertThat(result.maxDailyLoss()).isEqualByComparingTo(new BigDecimal("5.0"));
        assertThat(result.maxOpenPositions()).isEqualTo(3);
        assertThat(result.stopLossTypeId()).isEqualTo(slTypeId);
        assertThat(result.stopLossTypeCode()).isEqualTo("fixed_pct");
        assertThat(result.stopLoss()).isEqualByComparingTo(new BigDecimal("1.5"));
        assertThat(result.takeProfit()).isEqualByComparingTo(new BigDecimal("3.0"));
        assertThat(result.tradingWindowStart()).isEqualTo(LocalTime.of(9, 30));
        assertThat(result.tradingWindowEnd()).isEqualTo(LocalTime.of(16, 0));
        assertThat(result.useML()).isTrue();
        assertThat(result.mlStrategyId()).isEqualTo(mlId);
        assertThat(result.mlStrategyCode()).isEqualTo("lstm");
    }

    @Test
    void update_shouldModifyExistingStrategy() {
        UUID strategyId = UUID.randomUUID();
        var existing = new StrategyConfig(testUser, "Old Name", "OLD", BigDecimal.ONE, false);
        try {
            var idField = StrategyConfig.class.getDeclaredField("id");
            idField.setAccessible(true);
            idField.set(existing, strategyId);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        var request = new UpdateStrategyRequest(
            "New Name", "NEW", new BigDecimal("2.0"), true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            null, null
        );
        when(strategyRepository.findById(strategyId)).thenReturn(Optional.of(existing));
        var updated = new StrategyConfig(testUser, "New Name", "NEW", new BigDecimal("2.0"), true);
        when(strategyRepository.save(any())).thenReturn(updated);

        StrategyResponse result = service.update(strategyId, request);

        assertThat(result.name()).isEqualTo("New Name");
        assertThat(result.symbol()).isEqualTo("NEW");
        assertThat(result.maxPositionSize()).isEqualByComparingTo(new BigDecimal("2.0"));
        assertThat(result.enabled()).isTrue();
    }

    @Test
    void update_shouldThrowWhenNotFound() {
        UUID id = UUID.randomUUID();
        when(strategyRepository.findById(id)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.update(id, new UpdateStrategyRequest(
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            null, null
        ))).isInstanceOf(ResponseStatusException.class)
          .hasMessageContaining("Strategy not found");
    }

    @Test
    void delete_shouldRemoveStrategy() {
        UUID id = UUID.randomUUID();
        when(strategyRepository.existsById(id)).thenReturn(true);

        service.delete(id);

        verify(strategyRepository).deleteById(id);
    }

    @Test
    void delete_shouldThrowWhenNotFound() {
        UUID id = UUID.randomUUID();
        when(strategyRepository.existsById(id)).thenReturn(false);

        assertThatThrownBy(() -> service.delete(id))
            .isInstanceOf(ResponseStatusException.class)
            .hasMessageContaining("Strategy not found");
    }

    @Test
    void listStopLossTypes_shouldReturnAll() {
        when(stopLossTypeRepository.findAll()).thenReturn(List.of(slType));

        List<StopLossTypeResponse> result = service.listStopLossTypes();

        assertThat(result).hasSize(1);
        assertThat(result.get(0).code()).isEqualTo("fixed_pct");
        assertThat(result.get(0).displayName()).isEqualTo("Fixed %");
    }

    @Test
    void listMLStrategies_shouldReturnAll() {
        var ml = new MLStrategy("xgboost", "XGBoost", "Gradient boosting");
        when(mlStrategyRepository.findAll()).thenReturn(List.of(ml));

        List<MLStrategyResponse> result = service.listMLStrategies();

        assertThat(result).hasSize(1);
        assertThat(result.get(0).code()).isEqualTo("xgboost");
    }
}