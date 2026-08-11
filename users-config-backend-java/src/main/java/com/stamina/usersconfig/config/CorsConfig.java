package com.stamina.usersconfig.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class CorsConfig {

    // Comma-separated list of allowed origins, from CORS_ALLOWED_ORIGINS env var.
    // In production set it to your HTTPS domain(s), e.g.:
    //   CORS_ALLOWED_ORIGINS=https://stamina.example.com
    // In local dev the default keeps localhost working.
    @Value("${cors.allowed-origins:}")
    private String allowedOrigins;

    @Bean
    WebMvcConfigurer corsConfigurer() {
        return new WebMvcConfigurer() {
            @Override
            public void addCorsMappings(CorsRegistry registry) {
                String[] origins;
                if (allowedOrigins == null || allowedOrigins.isBlank()) {
                    // Default: local dev + Render `.onrender.com` origins.
                    // En producción se puede sobreescribir con CORS_ALLOWED_ORIGINS.
                    origins = new String[]{
                        "http://localhost:*",
                        "http://127.0.0.1:*",
                        "https://*.onrender.com"
                    };
                } else {
                    origins = allowedOrigins.split(",");
                }
                registry.addMapping("/**")
                  .allowedOriginPatterns(origins)
                    .allowedMethods("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")
                    .allowedHeaders("*")
                    .allowCredentials(true);
            }
        };
    }
}

