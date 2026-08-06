package com.stamina.usersconfig.user.dto;

import jakarta.validation.constraints.Email;

/**
 * Solicitud opcional para simular creación de usuario en entornos de prueba.
 */
public record SimulateCreateUserRequest(
    @Email String email,
    String displayName
) {
}
