package com.stamina.usersconfig.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class CryptoConfig {

    @Bean
    public CryptoService cryptoService() {
        String masterKey = System.getenv("CRYPTO_MASTER_KEY");
        if (masterKey == null || masterKey.isBlank()) {
            throw new IllegalStateException(
                "CRYPTO_MASTER_KEY environment variable is required. " +
                "Set it to a 32-character (256-bit) key for AES-256 encryption."
            );
        }
        return new CryptoService(masterKey);
    }
}
