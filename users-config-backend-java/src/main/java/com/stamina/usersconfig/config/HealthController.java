package com.stamina.usersconfig.config;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
public class HealthController {
    @GetMapping("/health")
    Map<String, String> health() {
        return Map.of(
            "service", "users-config-backend",
            "status", "ok"
        );
    }
}

