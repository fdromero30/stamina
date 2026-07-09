package com.stamina.usersconfig.trading.client;

import com.stamina.usersconfig.trading.config.EtoroConfig;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.util.Map;

@Component
public class EtoroClient {

    private final EtoroConfig config;
    private final RestClient restClient;

    public EtoroClient(EtoroConfig config) {
        this.config = config;
        this.restClient = RestClient.builder()
                .baseUrl(config.getApiBaseUrl())
                .defaultHeader("Authorization", "Bearer " + config.getApiKey())
                .build();
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> health() {
        if ("replace_me".equals(config.getApiKey())) {
            return Map.of("status", "not_configured", "broker", "etoro");
        }
        return restClient.get()
                .uri("/health")
                .retrieve()
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> placeOrder(String symbol, String side, double units) {
        var body = Map.of(
                "symbol", symbol,
                "side", side,
                "units", units,
                "order_type", "market"
        );
        return restClient.post()
                .uri("/accounts/{accountId}/orders", config.getAccountId())
                .body(body)
                .retrieve()
                .body(Map.class);
    }
}