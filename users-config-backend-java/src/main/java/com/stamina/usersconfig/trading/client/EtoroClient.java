package com.stamina.usersconfig.trading.client;

import com.stamina.usersconfig.apikey.entity.ApiKey;
import com.stamina.usersconfig.apikey.repository.ApiKeyRepository;
import com.stamina.usersconfig.config.CryptoService;
import com.stamina.usersconfig.trading.config.EtoroConfig;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@Component
public class EtoroClient {

    private final EtoroConfig config;
    private final RestClient restClient;
    private final ApiKeyRepository apiKeyRepository;
    private final CryptoService cryptoService;

    public EtoroClient(EtoroConfig config,
                       ApiKeyRepository apiKeyRepository,
                       CryptoService cryptoService) {
        this.config = config;
        this.apiKeyRepository = apiKeyRepository;
        this.cryptoService = cryptoService;
        this.restClient = RestClient.builder()
                .baseUrl(config.getApiBaseUrl())
                .build();
    }

    // ──────────────────────────────────────────────
    //  Internal: resolve eToro keys for a user
    // ──────────────────────────────────────────────

    private record EtoroCredentials(String publicApiKey, String userKey) {}

    private EtoroCredentials resolveCredentials(UUID userId) {
        List<ApiKey> keys = apiKeyRepository.findByUserId(userId);
        ApiKey etoroKey = keys.stream()
                .filter(k -> "etoro".equalsIgnoreCase(k.getBroker()))
                .findFirst()
                .orElseThrow(() -> new IllegalStateException(
                        "No eToro API key found for user " + userId));

        String publicPlain = cryptoService.decrypt(etoroKey.getEncryptedPublicKey());
        String privatePlain = cryptoService.decrypt(etoroKey.getEncryptedPrivateKey());
        return new EtoroCredentials(publicPlain, privatePlain);
    }

    private RestClient.RequestHeadersSpec<?> applyHeaders(RestClient.RequestHeadersSpec<?> spec,
                                                           UUID userId) {
        EtoroCredentials creds = resolveCredentials(userId);
        return spec.header("x-request-id", UUID.randomUUID().toString())
                   .header("x-api-key", creds.publicApiKey())
                   .header("x-user-key", creds.userKey());
    }

    // ──────────────────────────────────────────────
    //  Health check (no user-specific keys needed)
    // ──────────────────────────────────────────────

    public Map<String, Object> health() {
        try {
            return restClient.get()
                    .uri("/watchlists")
                    .header("x-request-id", UUID.randomUUID().toString())
                    .retrieve()
                    .body(Map.class);
        } catch (Exception e) {
            return Map.of("status", "unreachable", "broker", "etoro", "error", e.getMessage());
        }
    }

    // ──────────────────────────────────────────────
    //  Market Data
    // ──────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> searchInstruments(UUID userId, String query, String fields) {
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri(uriBuilder -> uriBuilder
                                .path("/market-data/search")
                                .queryParam("searchText", query)
                                .queryParam("fields", fields)
                                .build()),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getInstrumentRates(UUID userId, List<Integer> instrumentIds) {
        String ids = instrumentIds.stream()
                .map(String::valueOf)
                .reduce((a, b) -> a + "," + b)
                .orElse("");
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri("/market-data/instruments/rates?instrumentIds={ids}", ids),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getCandles(UUID userId, int instrumentId,
                                           String direction, String interval, int candlesCount) {
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri("/market-data/instruments/{instrumentId}/history/candles/{direction}/{interval}/{candlesCount}",
                                instrumentId, direction, interval, candlesCount),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ──────────────────────────────────────────────
    //  Trading Execution – Demo
    // ──────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> placeDemoMarketOrderByAmount(UUID userId,
                                                             int instrumentId,
                                                             boolean isBuy,
                                                             int leverage,
                                                             double amount) {
        Map<String, Object> body = Map.of(
                "InstrumentID", instrumentId,
                "IsBuy", isBuy,
                "Leverage", leverage,
                "Amount", amount
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution/demo/market-open-orders/by-amount")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> placeDemoMarketOrderByUnits(UUID userId,
                                                            int instrumentId,
                                                            boolean isBuy,
                                                            int leverage,
                                                            double units) {
        Map<String, Object> body = Map.of(
                "InstrumentID", instrumentId,
                "IsBuy", isBuy,
                "Leverage", leverage,
                "AmountInUnits", units
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution/demo/market-open-orders/by-units")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> closeDemoPosition(UUID userId, int positionId, Double unitsToDeduct) {
        Map<String, Object> body = Map.of(
                "InstrumentId", positionId,
                "UnitsToDeduct", unitsToDeduct
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution/demo/market-close-orders/positions/{positionId}", positionId)
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ──────────────────────────────────────────────
    //  Trading Execution – Real
    // ──────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> placeMarketOrderByAmount(UUID userId,
                                                         int instrumentId,
                                                         boolean isBuy,
                                                         int leverage,
                                                         double amount) {
        Map<String, Object> body = Map.of(
                "InstrumentID", instrumentId,
                "IsBuy", isBuy,
                "Leverage", leverage,
                "Amount", amount
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution/market-open-orders/by-amount")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> placeMarketOrderByUnits(UUID userId,
                                                        int instrumentId,
                                                        boolean isBuy,
                                                        int leverage,
                                                        double units) {
        Map<String, Object> body = Map.of(
                "InstrumentID", instrumentId,
                "IsBuy", isBuy,
                "Leverage", leverage,
                "AmountInUnits", units
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution/market-open-orders/by-units")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> closePosition(UUID userId, int positionId, Double unitsToDeduct) {
        Map<String, Object> body = Map.of(
                "InstrumentId", positionId,
                "UnitsToDeduct", unitsToDeduct
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution/market-close-orders/positions/{positionId}", positionId)
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> cancelOpenOrder(UUID userId, int orderId, boolean demo) {
        String path = demo
                ? "/trading/execution/demo/market-open-orders/{orderId}"
                : "/trading/execution/market-open-orders/{orderId}";
        return (Map<String, Object>) applyHeaders(
                restClient.delete().uri(path, orderId),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ──────────────────────────────────────────────
    //  Portfolio / P&L
    // ──────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> getPortfolio(UUID userId) {
        return (Map<String, Object>) applyHeaders(
                restClient.get().uri("/trading/info/portfolio"),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getDemoPortfolio(UUID userId) {
        return (Map<String, Object>) applyHeaders(
                restClient.get().uri("/trading/info/demo/portfolio"),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getRealPnl(UUID userId) {
        return (Map<String, Object>) applyHeaders(
                restClient.get().uri("/trading/info/real/pnl"),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getDemoPnl(UUID userId) {
        return (Map<String, Object>) applyHeaders(
                restClient.get().uri("/trading/info/demo/pnl"),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getTradeHistory(UUID userId, String minDate, int page, int pageSize) {
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri(uriBuilder -> uriBuilder
                                .path("/trading/info/trade/history")
                                .queryParam("minDate", minDate)
                                .queryParam("page", page)
                                .queryParam("pageSize", pageSize)
                                .build()),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ──────────────────────────────────────────────
    //  User Info
    // ──────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> getUserInfo(UUID userId, String usernames) {
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri("/user-info/people?usernames={usernames}", usernames),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ──────────────────────────────────────────────
    //  Place order (legacy method used by TradingService)
    // ──────────────────────────────────────────────

    public Map<String, Object> placeOrder(UUID userId, String symbol, String side, double units) {
        Map<String, Object> searchResult = searchInstruments(userId, symbol, "instrumentId,internalSymbolFull,displayname");
        return Map.of(
                "searchResult", searchResult,
                "symbol", symbol,
                "side", side,
                "units", units
        );
    }
}