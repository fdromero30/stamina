package com.stamina.usersconfig.trading.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Configuration
@ConfigurationProperties(prefix = "etoro")
public class EtoroConfig {

    private String apiBaseUrl = "https://public-api.etoro.com/api/v1";

    /**
     * When true, the client returns mock data instead of calling the real
     * eToro API.  Useful for local development and testing without real
     * eToro credentials.
     */
    private boolean mock = false;

    public String getApiBaseUrl() {
        return apiBaseUrl;
    }

    public void setApiBaseUrl(String apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
    }

    public boolean isMock() {
        return mock;
    }

    public void setMock(boolean mock) {
        this.mock = mock;
    }
}
