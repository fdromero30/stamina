package com.stamina.usersconfig.strategy.controller;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.stamina.usersconfig.strategy.dto.CreateStrategyRequest;
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
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;

import java.math.BigDecimal;
import java.time.LocalTime;

import static org.hamcrest.Matchers.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@SpringBootTest
@AutoConfigureMockMvc
@WithMockUser
class StrategyConfigControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private AppUserRepository userRepository;

    @Autowired
    private StrategyConfigRepository strategyRepository;

    @Autowired
    private StopLossTypeRepository stopLossTypeRepository;

    @Autowired
    private MLStrategyRepository mlStrategyRepository;

    private AppUser testUser;
    private StopLossType slType;

    @BeforeEach
    void setUp() {
        strategyRepository.deleteAll();
        userRepository.deleteAll();
        stopLossTypeRepository.deleteAll();
        mlStrategyRepository.deleteAll();

        testUser = userRepository.save(new AppUser("strat-test@test.com", "Strategy Tester", "password"));
        slType = stopLossTypeRepository.save(new StopLossType("trailing", "Trailing", "Trailing stop loss"));
    }

    @Test
    void listStrategies_shouldReturnEmptyList() throws Exception {
        mockMvc.perform(get("/strategies?userId=" + testUser.getId()))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(0)));
    }

    @Test
    void createStrategy_shouldReturnCreated() throws Exception {
        var request = new CreateStrategyRequest(
            testUser.getId(), "Test Strat", "BTCUSDT", new BigDecimal("0.5"), true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            false, null
        );

        mockMvc.perform(post("/strategies")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name", is("Test Strat")))
            .andExpect(jsonPath("$.symbol", is("BTCUSDT")))
            .andExpect(jsonPath("$.maxPositionSize", is(0.5)))
            .andExpect(jsonPath("$.enabled", is(true)));
    }

    @Test
    void createStrategy_withAllOptionalFields_shouldReturnCreated() throws Exception {
        var request = new CreateStrategyRequest(
            testUser.getId(), "Full Strat", "ETHUSDT", new BigDecimal("1.0"), true,
            new BigDecimal("15.0"), new BigDecimal("2.5"), new BigDecimal("5.0"), 5,
            slType.getId(), new BigDecimal("2.0"), new BigDecimal("4.0"), new BigDecimal("0.0005"),
            LocalTime.of(8, 0), LocalTime.of(18, 0), new BigDecimal("3.0"), new BigDecimal("1.5"),
            false, null
        );

        mockMvc.perform(post("/strategies")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.name", is("Full Strat")))
            .andExpect(jsonPath("$.maxDrawdown", is(15.0)))
            .andExpect(jsonPath("$.maxRiskPerTrade", is(2.5)))
            .andExpect(jsonPath("$.maxDailyLoss", is(5.0)))
            .andExpect(jsonPath("$.maxOpenPositions", is(5)))
            .andExpect(jsonPath("$.stopLossTypeCode", is("trailing")))
            .andExpect(jsonPath("$.stopLoss", is(2.0)))
            .andExpect(jsonPath("$.takeProfit", is(4.0)))
            .andExpect(jsonPath("$.tradingWindowStart", is("08:00:00")))
            .andExpect(jsonPath("$.tradingWindowEnd", is("18:00:00")));
    }

    @Test
    void createStrategy_withML_shouldReturnCreated() throws Exception {
        var mlStrategy = mlStrategyRepository.save(new MLStrategy("lstm", "LSTM", "LSTM model"));

        var request = new CreateStrategyRequest(
            testUser.getId(), "ML Strat", "SOLUSDT", new BigDecimal("2.0"), true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            true, mlStrategy.getId()
        );

        mockMvc.perform(post("/strategies")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isCreated())
            .andExpect(jsonPath("$.useML", is(true)))
            .andExpect(jsonPath("$.mlStrategyCode", is("lstm")))
            .andExpect(jsonPath("$.mlStrategyDisplayName", is("LSTM")));
    }

    @Test
    void createStrategy_shouldReturn400WhenMissingRequired() throws Exception {
        var request = new CreateStrategyRequest(
            testUser.getId(), "", "", null, true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            false, null
        );

        mockMvc.perform(post("/strategies")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(request)))
            .andExpect(status().isBadRequest());
    }

    @Test
    void updateStrategy_shouldModifyAndReturn() throws Exception {
        var strategy = strategyRepository.save(
            new StrategyConfig(testUser, "Original", "ORIG", BigDecimal.ONE, false));

        var updateRequest = new UpdateStrategyRequest(
            "Updated", "UPD", new BigDecimal("3.0"), true,
            null, null, null, null,
            null, null, null, null,
            null, null, null, null,
            null, null
        );

        mockMvc.perform(put("/strategies/{id}", strategy.getId())
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(updateRequest)))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.name", is("Updated")))
            .andExpect(jsonPath("$.symbol", is("UPD")))
            .andExpect(jsonPath("$.maxPositionSize", is(3.0)))
            .andExpect(jsonPath("$.enabled", is(true)));
    }

    @Test
    void deleteStrategy_shouldRemoveAndReturnNoContent() throws Exception {
        var strategy = strategyRepository.save(
            new StrategyConfig(testUser, "To Delete", "DEL", BigDecimal.ONE, false));

        mockMvc.perform(delete("/strategies/{id}", strategy.getId()))
            .andExpect(status().isNoContent());

        mockMvc.perform(get("/strategies?userId=" + testUser.getId()))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(0)));
    }

    @Test
    void listStopLossTypes_shouldReturnSeededTypes() throws Exception {
        mockMvc.perform(get("/strategies/stop-loss-types"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(greaterThanOrEqualTo(1))))
            .andExpect(jsonPath("$[0].code", notNullValue()))
            .andExpect(jsonPath("$[0].displayName", notNullValue()));
    }

    @Test
    void listMLStrategies_shouldReturnEmptyList() throws Exception {
        mockMvc.perform(get("/strategies/ml-strategies"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$", hasSize(0)));
    }
}