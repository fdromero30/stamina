package com.stamina.usersconfig.user.service;

import com.stamina.usersconfig.strategy.service.StrategyConfigService;
import com.stamina.usersconfig.user.dto.CreateUserRequest;
import com.stamina.usersconfig.user.dto.LoginRequest;
import com.stamina.usersconfig.user.dto.UserResponse;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import com.stamina.usersconfig.user.exception.InvalidCredentialsException;
import com.stamina.usersconfig.user.exception.UserAlreadyExistsException;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.UUID;

@Service
public class AppUserService {

    /** Usuario y contraseña del seeder para pruebas locales. */
    private static final String DEFAULT_TEST_EMAIL = "alice@stamina.local";
    private static final String DEFAULT_TEST_PASSWORD = "stamina123";
    private static final String DEFAULT_TEST_DISPLAY_NAME = "Usuario de prueba";
    private static final String TEST_EMAIL_DOMAIN = "@stamina.local";

    private final AppUserRepository repository;
    private final PasswordEncoder passwordEncoder;
    private final StrategyConfigService strategyConfigService;

    public AppUserService(AppUserRepository repository,
                          PasswordEncoder passwordEncoder,
                          StrategyConfigService strategyConfigService) {
        this.repository = repository;
        this.passwordEncoder = passwordEncoder;
        this.strategyConfigService = strategyConfigService;
    }

    public List<UserResponse> listAll() {
        return repository.findAll().stream()
                .map(UserResponse::fromEntity)
                .toList();
    }

    public UserResponse create(CreateUserRequest request) {
        String email = normalizeEmail(request.email());
        if (repository.existsByEmail(email)) {
            throw new UserAlreadyExistsException(
                    "The email address '" + email + "' is already registered.");
        }
        String hashedPassword = passwordEncoder.encode(request.password());
        AppUser saved = repository.save(new AppUser(email, request.displayName(), hashedPassword));

        // Asignar la estrategia default de la app para que el sistema nunca
        // quede sin estrategias configuradas (evita que el bot/UI se rompa).
        strategyConfigService.ensureDefaultStrategy(saved.getId());

        return UserResponse.fromEntity(saved);
    }

    public UserResponse login(LoginRequest request) {
        AppUser user = repository.findByEmail(normalizeEmail(request.email()))
                .orElseThrow(() -> new InvalidCredentialsException("Invalid email or password."));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new InvalidCredentialsException("Invalid email or password.");
        }

        return UserResponse.fromEntity(user);
    }

    /**
     * Simula un inicio de sesión reutilizando {@link #login(LoginRequest)} con credenciales de prueba.
     * Si no se indica email, usa el usuario por defecto del seeder.
     */
    public UserResponse simulateLogin(String email) {
        try {
            return login(new LoginRequest(
                    resolveTextOrDefault(email, DEFAULT_TEST_EMAIL),
                    DEFAULT_TEST_PASSWORD
            ));
        } catch (RuntimeException ex) {
            throw rethrowSimulationError(ex, "No se pudo simular el inicio de sesión.");
        }
    }

    /**
     * Simula la creación de un usuario reutilizando {@link #create(CreateUserRequest)}.
     * Si no se indica email, genera uno único para evitar conflictos en pruebas repetidas.
     */
    public UserResponse simulateCreateUser(String email, String displayName) {
        try {
            return create(new CreateUserRequest(
                    resolveTextOrDefault(email, generateUniqueTestEmail()),
                    resolveTextOrDefault(displayName, DEFAULT_TEST_DISPLAY_NAME),
                    DEFAULT_TEST_PASSWORD
            ));
        } catch (RuntimeException ex) {
            throw rethrowSimulationError(ex, "No se pudo simular la creación del usuario.");
        }
    }

    private static String normalizeEmail(String email) {
        return email.trim();
    }

    private static String resolveTextOrDefault(String value, String defaultValue) {
        if (value == null || value.isBlank()) {
            return defaultValue;
        }
        return value.trim();
    }

    private static String generateUniqueTestEmail() {
        return "test-" + UUID.randomUUID() + TEST_EMAIL_DOMAIN;
    }

    private static RuntimeException rethrowSimulationError(RuntimeException ex, String message) {
        if (ex instanceof InvalidCredentialsException || ex instanceof UserAlreadyExistsException) {
            return ex;
        }
        return new IllegalStateException(message, ex);
    }
}