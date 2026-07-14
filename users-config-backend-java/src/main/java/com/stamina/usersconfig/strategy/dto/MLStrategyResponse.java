package com.stamina.usersconfig.strategy.dto;

import com.stamina.usersconfig.strategy.entity.MLStrategy;

import java.util.UUID;

public record MLStrategyResponse(
    UUID id,
    String code,
    String displayName,
    String description
) {
    public static MLStrategyResponse fromEntity(MLStrategy entity) {
        return new MLStrategyResponse(entity.getId(), entity.getCode(), entity.getDisplayName(), entity.getDescription());
    }
}