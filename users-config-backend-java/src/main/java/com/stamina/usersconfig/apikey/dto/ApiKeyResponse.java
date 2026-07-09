package com.stamina.usersconfig.apikey.dto;

import java.time.Instant;
import java.util.UUID;

public record ApiKeyResponse(
    UUID id,
    String label,
    String broker,
    String maskedKey,
    Instant createdAt
) {
}
