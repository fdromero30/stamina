package com.stamina.usersconfig.user.dto;

import com.stamina.usersconfig.user.entity.AppUser;

import java.time.Instant;
import java.util.UUID;

public record UserResponse(
    UUID id,
    String email,
    String displayName,
    Instant createdAt
) {
    public static UserResponse fromEntity(AppUser user) {
        return new UserResponse(
            user.getId(),
            user.getEmail(),
            user.getDisplayName(),
            user.getCreatedAt()
        );
    }
}