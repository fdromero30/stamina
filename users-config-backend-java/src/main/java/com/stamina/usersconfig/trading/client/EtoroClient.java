package com.stamina.usersconfig.trading.client;

import com.stamina.usersconfig.apikey.entity.ApiKey;
import com.stamina.usersconfig.apikey.repository.ApiKeyRepository;
import com.stamina.usersconfig.config.CryptoService;
import com.stamina.usersconfig.trading.config.EtoroConfig;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.math.BigDecimal;
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
        if (config.isMock()) {
            return mockSearchInstruments(query);
        }
        // The /market-data/search endpoint does not filter results reliably.
        // Use /market-data/instruments which returns instrumentDisplayDatas
        // with the correct instrumentID for the searched symbol.
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri(uriBuilder -> uriBuilder
                                .path("/market-data/instruments")
                                .queryParam("searchText", query)
                                .queryParam("fields", fields)
                                .build()),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ── Mock data for local development (no real eToro credentials) ──

    private Map<String, Object> mockSearchInstruments(String query) {
        String q = query.toLowerCase().replace("/", "");
        // Map common symbols to mock instrument IDs.
        // Forex pairs use negative IDs (eToro convention); crypto/indices use positive.
        record InstrumentDef(int id, String symbolFull, String displayName) {}
        InstrumentDef[] defs = {
            new InstrumentDef(-100000, "EURUSD", "EUR/USD"),
            new InstrumentDef(-100001, "GBPUSD", "GBP/USD"),
            new InstrumentDef(-100002, "XAUUSD", "XAU/USD"),
            new InstrumentDef(2, "BTC", "BTC"),
            new InstrumentDef(3, "ETH", "ETH"),
            new InstrumentDef(4, "AAPL", "AAPL"),
            new InstrumentDef(5, "TSLA", "TSLA"),
            new InstrumentDef(6, "SPX500", "SPX500"),
        };
        for (InstrumentDef d : defs) {
            if (d.symbolFull.contains(q) || d.displayName.toLowerCase().contains(q)) {
                return Map.of(
                    "instrumentDisplayDatas", List.of(Map.of(
                        "instrumentID", d.id,
                        "instrumentDisplayName", d.displayName,
                        "symbolFull", d.symbolFull,
                        "instrumentTypeID", d.id < 0 ? 1 : 5
                    ))
                );
            }
        }
        // Fallback: return EUR/USD
        return Map.of(
            "instrumentDisplayDatas", List.of(Map.of(
                "instrumentID", -100000,
                "instrumentDisplayName", "EUR/USD",
                "symbolFull", "EURUSD",
                "instrumentTypeID", 1
            ))
        );
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getInstrumentRates(UUID userId, List<Integer> instrumentIds) {
        if (config.isMock()) {
            return mockRates(instrumentIds);
        }
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
        if (config.isMock()) {
            return mockCandles(instrumentId, interval, candlesCount);
        }
        return (Map<String, Object>) applyHeaders(
                restClient.get()
                        .uri("/market-data/instruments/{instrumentId}/history/candles/{direction}/{interval}/{candlesCount}",
                                instrumentId, direction, interval, candlesCount),
                userId)
                .retrieve()
                .body(Map.class);
    }

    // ── Mock rates & candles ──────────────────────────────────────

    private Map<String, Object> mockRates(List<Integer> instrumentIds) {
        List<Map<String, Object>> rates = new java.util.ArrayList<>();
        for (Integer id : instrumentIds) {
            double base = mockBasePrice(id);
            double spread = base * 0.0002;
            rates.add(Map.of(
                "InstrumentID", id,
                "Bid", base,
                "Ask", base + spread
            ));
        }
        return Map.of("Rates", rates);
    }

    private Map<String, Object> mockCandles(int instrumentId, String interval, int candlesCount) {
        double base = mockBasePrice(instrumentId);
        List<Map<String, Object>> candles = new java.util.ArrayList<>();
        java.time.Instant now = java.time.Instant.now();
        long stepSeconds = intervalToSeconds(interval);
        double price = base;
        for (int i = candlesCount; i >= 1; i--) {
            java.time.Instant ts = now.minusSeconds(stepSeconds * i);
            // Generate a small random walk around the base price
            double open = price;
            double close = price + (Math.random() - 0.5) * base * 0.002;
            double high = Math.max(open, close) + Math.random() * base * 0.001;
            double low = Math.min(open, close) - Math.random() * base * 0.001;
            price = close;
            candles.add(Map.of(
                "Open", open,
                "High", high,
                "Low", low,
                "Close", close,
                "FromDateISO", ts.toString()
            ));
        }
        return Map.of("Candles", candles);
    }

    private double mockBasePrice(int instrumentId) {
        return switch (instrumentId) {
            case -100000 -> 1.0850;   // EUR/USD
            case -100001 -> 1.2700;   // GBP/USD
            case -100002 -> 2350.0;   // XAU/USD
            case 2 -> 67000.0;        // BTC
            case 3 -> 3500.0;         // ETH
            case 4 -> 220.0;          // AAPL
            case 5 -> 250.0;          // TSLA
            case 6 -> 5500.0;         // SPX500
            default -> 100.0;
        };
    }

    private long intervalToSeconds(String interval) {
        return switch (interval) {
            case "OneMinute" -> 60L;
            case "FiveMinutes" -> 300L;
            case "FifteenMinutes" -> 900L;
            case "ThirtyMinutes" -> 1800L;
            case "OneHour" -> 3600L;
            case "FourHours" -> 14400L;
            case "OneDay" -> 86400L;
            case "OneWeek" -> 604800L;
            default -> 300L;
        };
    }

    // ──────────────────────────────────────────────
    //  Trading Execution — one method per operation.
    //  The `demo` flag (from request/ETORO_DEMO) selects the
    //  upstream path: /demo/ for Virtual, non-demo for Real.
    // ──────────────────────────────────────────────

    /** Upstream path segment: "/demo" for the Virtual portfolio, "" for Real. */
    private static String demoSegment(boolean demo) {
        return demo ? "/demo" : "";
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> placeMarketOrderByAmount(UUID userId,
                                                         int instrumentId,
                                                         boolean isBuy,
                                                         int leverage,
                                                         double amount,
                                                         boolean demo) {
        Map<String, Object> body = Map.of(
                "InstrumentID", instrumentId,
                "IsBuy", isBuy,
                "Leverage", leverage,
                "Amount", amount
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution" + demoSegment(demo) + "/market-open-orders/by-amount")
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
                                                        double units,
                                                        boolean demo) {
        Map<String, Object> body = Map.of(
                "InstrumentID", instrumentId,
                "IsBuy", isBuy,
                "Leverage", leverage,
                "AmountInUnits", units
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution" + demoSegment(demo) + "/market-open-orders/by-units")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    /**
     * Market-if-touched (limit) order. Per the eToro API docs the endpoint is
     * /trading/execution[/demo]/limit-orders and the trigger price field is
     * {@code Rate} (NOT {@code LimitRate}).
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> placeLimitOrderByUnits(UUID userId,
                                                       int instrumentId,
                                                       boolean isBuy,
                                                       int leverage,
                                                       double units,
                                                       java.math.BigDecimal rate,
                                                       java.math.BigDecimal stopLossRate,
                                                       java.math.BigDecimal takeProfitRate,
                                                       boolean demo) {
        Map<String, Object> body = new java.util.HashMap<>();
        body.put("InstrumentID", instrumentId);
        body.put("IsBuy", isBuy);
        body.put("Leverage", leverage);
        body.put("AmountInUnits", units);
        body.put("Rate", rate);
        if (stopLossRate != null) body.put("StopLossRate", stopLossRate);
        if (takeProfitRate != null) body.put("TakeProfitRate", takeProfitRate);
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution" + demoSegment(demo) + "/limit-orders")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> closePosition(UUID userId, int positionId, Double unitsToDeduct, boolean demo) {
        Map<String, Object> body = Map.of(
                "InstrumentId", positionId,
                "UnitsToDeduct", unitsToDeduct
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution" + demoSegment(demo) + "/market-close-orders/positions/{positionId}", positionId)
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> cancelOpenOrder(UUID userId, int orderId, boolean demo) {
        String path = "/trading/execution" + demoSegment(demo) + "/market-open-orders/{orderId}";
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
    public Map<String, Object> getPortfolio(UUID userId, boolean demo) {
        return (Map<String, Object>) applyHeaders(
                restClient.get().uri("/trading/info" + demoSegment(demo) + "/portfolio"),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getPnl(UUID userId, boolean demo) {
        String path = demo
                ? "/trading/info/demo/pnl"
                : "/trading/info/real/pnl";
        return (Map<String, Object>) applyHeaders(
                restClient.get().uri(path),
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
    //  Stop Loss / Take Profit Management
    // ──────────────────────────────────────────────

    @SuppressWarnings("unchecked")
    public Map<String, Object> setStopLoss(UUID userId, int positionId, BigDecimal stopLossRate, boolean demo) {
        Map<String, Object> body = Map.of(
                "PositionID", positionId,
                "StopLossRate", stopLossRate
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution" + demoSegment(demo) + "/stop-loss-orders")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> setTakeProfit(UUID userId, int positionId, BigDecimal takeProfitRate, boolean demo) {
        Map<String, Object> body = Map.of(
                "PositionID", positionId,
                "TakeProfitRate", takeProfitRate
        );
        return (Map<String, Object>) applyHeaders(
                restClient.post()
                        .uri("/trading/execution" + demoSegment(demo) + "/take-profit-orders")
                        .body(body),
                userId)
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> updateStopLoss(UUID userId, int positionId, BigDecimal newStopLossRate, boolean demo) {
        Map<String, Object> body = Map.of(
                "PositionID", positionId,
                "StopLossRate", newStopLossRate
        );
        return (Map<String, Object>) applyHeaders(
                restClient.put()
                        .uri("/trading/execution" + demoSegment(demo) + "/stop-loss-orders/{positionId}", positionId)
                        .body(body),
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
