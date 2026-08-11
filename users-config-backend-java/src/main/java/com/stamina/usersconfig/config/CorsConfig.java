package com.stamina.usersconfig.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.util.Arrays;

@Configuration
public class CorsConfig {

    // Comma-separated list of allowed origins, from CORS_ALLOWED_ORIGINS env var.
    // In production set it to your HTTPS domain(s), e.g.:
    //   CORS_ALLOWED_ORIGINS=https://stamina.example.com
    // In local dev the default keeps localhost working.
    @Value("${cors.allowed-origins:}")
    private String allowedOrigins;

    // Spring Security 6 necesita un bean CorsConfigurationSource para
    // integrarse con .cors(cors -> {}) en SecurityConfig.
    @Bean
    CorsConfigurationSource corsConfigurationSource() {
        CorsConfiguration configuration = new CorsConfiguration();
        if (allowedOrigins == null || allowedOrigins.isBlank()) {
            configuration.setAllowedOriginPatterns(Arrays.asList(
                "http://localhost:*",
                "http://127.0.0.1:*",
                "https://*.onrender.com"
            ));
        } else {
            configuration.setAllowedOriginPatterns(Arrays.asList(allowedOrigins.split(",")));
        }
        configuration.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"));
        configuration.setAllowedHeaders(Arrays.asList("*"));
        configuration.setAllowCredentials(true);
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", configuration);
        return source;
    }

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

