package com.stamina.usersconfig.user.service;

import com.stamina.usersconfig.user.dto.CreateUserRequest;
import com.stamina.usersconfig.user.dto.UserResponse;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import com.stamina.usersconfig.user.exception.UserAlreadyExistsException;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class AppUserService {

    private final AppUserRepository repository;

    public AppUserService(AppUserRepository repository) {
        this.repository = repository;
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
        AppUser user = new AppUser(request.email(), request.displayName());
        AppUser saved = repository.save(user);
        return UserResponse.fromEntity(saved);
    }
}