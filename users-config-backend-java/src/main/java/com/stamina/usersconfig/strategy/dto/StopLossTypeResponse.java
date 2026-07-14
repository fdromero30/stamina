package com.stamina.usersconfig.strategy.dto;

import com.stamina.usersconfig.strategy.entity.StopLossType;

import java.util.UUID;

public record StopLossTypeResponse(
    UUID id,
    String code,
    String displayName,
    String description
) {
    public static StopLossTypeResponse fromEntity(StopLossType entity) {
        return new StopLossTypeResponse(entity.getId(), entity.getCode(), entity.getDisplayName(), entity.getDescription());
    }
}