package com.stamina.usersconfig.trading.service;

import com.stamina.usersconfig.trading.client.EtoroClient;
import com.stamina.usersconfig.trading.config.EtoroConfig;
import com.stamina.usersconfig.trading.dto.ExecuteTradeRequest;
import com.stamina.usersconfig.trading.dto.ExecuteTradeResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.math.BigDecimal;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyBoolean;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class TradingServiceTest {

    private static final String USER_ID = "00000000-0000-0000-0000-000000000000";
    private static final String STATUS_SUCCESS = "success";

    @Mock
    private EtoroClient etoroClient;

    private EtoroConfig etoroConfig;
    private TradingService service;

    @BeforeEach
    void setUp() {
        etoroConfig = new EtoroConfig();
        service = new TradingService(null, etoroClient, etoroConfig);
    }

    private ExecuteTradeRequest marketRequest(Boolean demo) {
        return new ExecuteTradeRequest(
                USER_ID,
                100000,
                true,
                10.0,
                1,
                BigDecimal.ONE,
                BigDecimal.TEN,
                BigDecimal.valueOf(1.5),
                "market",
                null,
                demo);
    }

    private void stubMarketOrderSuccess() {
        when(etoroClient.placeMarketOrderByUnits(
                any(UUID.class), anyInt(), anyBoolean(), anyInt(), any(Double.class), anyBoolean()))
                .thenReturn(Map.of("PositionID", 1234));
    }

    @Test
    void executeSmart_marketOrder_deberiaPasarDemoTrueCuandoRequestPideDemo() {
        stubMarketOrderSuccess();

        ExecuteTradeResponse response = service.executeSmart(marketRequest(true));

        assertThat(response.status()).isEqualTo(STATUS_SUCCESS);
        assertThat(response.demo()).isTrue();
        verify(etoroClient).placeMarketOrderByUnits(
                UUID.fromString(USER_ID), 100000, true, 1, 10.0, true);
    }

    @Test
    void executeSmart_marketOrder_deberiaPasarDemoFalseCuandoRequestPideReal() {
        stubMarketOrderSuccess();

        ExecuteTradeResponse response = service.executeSmart(marketRequest(false));

        assertThat(response.status()).isEqualTo(STATUS_SUCCESS);
        assertThat(response.demo()).isFalse();
        verify(etoroClient).placeMarketOrderByUnits(
                UUID.fromString(USER_ID), 100000, true, 1, 10.0, false);
    }

    @Test
    void executeSmart_marketOrder_sinDemo_deberiaUsarConfigEtoroDemo() {
        etoroConfig.setDemoMode(false);
        stubMarketOrderSuccess();

        ExecuteTradeResponse response = service.executeSmart(marketRequest(null));

        assertThat(response.status()).isEqualTo(STATUS_SUCCESS);
        assertThat(response.demo()).isFalse();
        // demo ausente en request → cae al valor ETORO_DEMO (false)
        verify(etoroClient).placeMarketOrderByUnits(
                UUID.fromString(USER_ID), 100000, true, 1, 10.0, false);
    }

    @Test
    void executeSmart_marketOrder_demoPorDefectoTrue() {
        stubMarketOrderSuccess();

        ExecuteTradeResponse response = service.executeSmart(marketRequest(null));

        assertThat(response.status()).isEqualTo(STATUS_SUCCESS);
        assertThat(response.demo()).isTrue();
        verify(etoroClient).placeMarketOrderByUnits(
                UUID.fromString(USER_ID), 100000, true, 1, 10.0, true);
    }

    @Test
    void executeSmart_limitOrder_deberiaUsarMetodoUnificadoConRate() {
        ExecuteTradeRequest request = new ExecuteTradeRequest(
                USER_ID,
                100000,
                true,
                10.0,
                1,
                BigDecimal.ONE,
                BigDecimal.TEN,
                BigDecimal.valueOf(1.5),
                "limit",
                BigDecimal.valueOf(1.10),
                true);

        when(etoroClient.placeLimitOrderByUnits(
                any(UUID.class), anyInt(), anyBoolean(), anyInt(), any(Double.class),
                any(BigDecimal.class), any(), any(), anyBoolean()))
                .thenReturn(Map.of("OrderID", 99));

        ExecuteTradeResponse response = service.executeSmart(request);

        assertThat(response.status()).isEqualTo(STATUS_SUCCESS);
        assertThat(response.positionId()).isEqualTo(99);
        verify(etoroClient).placeLimitOrderByUnits(
                UUID.fromString(USER_ID), 100000, true, 1, 10.0,
                BigDecimal.valueOf(1.10), BigDecimal.ONE, BigDecimal.TEN, true);
    }
}