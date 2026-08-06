package com.stamina.usersconfig.user.dto;

import jakarta.validation.constraints.Email;

/**
 * Solicitud opcional para simular inicio de sesión en entornos de prueba.
 */
public record SimulateLoginRequest(
    @Email String email
) {
}
