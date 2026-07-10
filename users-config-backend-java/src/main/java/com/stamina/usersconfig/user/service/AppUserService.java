package com.stamina.usersconfig.user.service;

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

@Service
public class AppUserService {

    private final AppUserRepository repository;
    private final PasswordEncoder passwordEncoder;

    public AppUserService(AppUserRepository repository, PasswordEncoder passwordEncoder) {
        this.repository = repository;
        this.passwordEncoder = passwordEncoder;
    }

    public List<UserResponse> listAll() {

        return repository.findAll()
                .stream()
                .map(UserResponse::fromEntity)
                .toList();
    }

    public UserResponse create(CreateUserRequest request) {
        if (repository.existsByEmail(request.email().trim())) {
            throw new UserAlreadyExistsException("The email address '" + request.email() + "' is already registered.");
        }
        String hashedPassword = passwordEncoder.encode(request.password());
        AppUser user = new AppUser(request.email(), request.displayName(), hashedPassword);
        AppUser saved = repository.save(user);
        return UserResponse.fromEntity(saved);
    }

    public UserResponse login(LoginRequest request) {
        AppUser user = repository.findByEmail(request.email().trim())
                .orElseThrow(() -> new InvalidCredentialsException("Invalid email or password."));

        if (!passwordEncoder.matches(request.password(), user.getPassword())) {
            throw new InvalidCredentialsException("Invalid email or password.");
        }

        return UserResponse.fromEntity(user);
    }
}
