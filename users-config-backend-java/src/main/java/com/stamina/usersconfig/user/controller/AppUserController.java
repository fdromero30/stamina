package com.stamina.usersconfig.user.controller;

import com.stamina.usersconfig.user.dto.CreateUserRequest;
import com.stamina.usersconfig.user.dto.LoginRequest;
import com.stamina.usersconfig.user.dto.SimulateCreateUserRequest;
import com.stamina.usersconfig.user.dto.SimulateLoginRequest;
import com.stamina.usersconfig.user.dto.UserResponse;
import com.stamina.usersconfig.user.service.AppUserService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/users")
public class AppUserController {

    private final AppUserService userService;

    public AppUserController(AppUserService userService) {
        this.userService = userService;
    }

    @GetMapping
    List<UserResponse> list() {
        return userService.listAll();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    UserResponse create(@Valid @RequestBody CreateUserRequest request) {
        return userService.create(request);
    }

    @PostMapping("/login")
    UserResponse login(@Valid @RequestBody LoginRequest request) {
        return userService.login(request);
    }

    /** Solo pruebas: inicia sesión con credenciales del seeder sin enviar contraseña. */
    @PostMapping("/login/simulate")
    UserResponse simulateLogin(@RequestBody(required = false) SimulateLoginRequest request) {
        String email = request != null ? request.email() : null;
        return userService.simulateLogin(email);
    }

    /** Solo pruebas: crea un usuario con datos por defecto sin enviar contraseña. */
    @PostMapping("/create/simulate")
    @ResponseStatus(HttpStatus.CREATED)
    UserResponse simulateCreateUser(@RequestBody(required = false) SimulateCreateUserRequest request) {
        String email = request != null ? request.email() : null;
        String displayName = request != null ? request.displayName() : null;
        return userService.simulateCreateUser(email, displayName);
    }
}
