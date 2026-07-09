package com.stamina.usersconfig.apikey.dto;

import jakarta.validation.constraints.NotBlank;

public record CreateApiKeyRequest(
    @NotBlank String userId,
    @NotBlank String label,
    @NotBlank String broker,
    @NotBlank String apiKey
) {
}