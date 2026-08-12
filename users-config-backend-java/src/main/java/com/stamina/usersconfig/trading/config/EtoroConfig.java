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

    /**
     * When true (default), trading operations are executed against the eToro
     * DEMO account instead of the real account.  The whole stack currently
     * runs against a demo account; real execution routes return
     * 404 RouteNotFound for demo keys.  Overridable via ETORO_DEMO.
     */
    private boolean demoMode = true;

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

    public boolean isDemoMode() {
        return demoMode;
    }

    public void setDemoMode(boolean demoMode) {
        this.demoMode = demoMode;
    }
}
