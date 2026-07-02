package com.stamina.usersconfig.user;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/users")
public class AppUserController {
    private final AppUserRepository repository;

    public AppUserController(AppUserRepository repository) {
        this.repository = repository;
    }

    @GetMapping
    List<AppUser> list() {
        return repository.findAll();
    }

    @PostMapping
    AppUser create(@Valid @RequestBody CreateUserRequest request) {
        AppUser user = new AppUser();
        user.setEmail(request.email());
        user.setDisplayName(request.displayName());
        return repository.save(user);
    }

    record CreateUserRequest(
        @Email @NotBlank String email,
        @NotBlank String displayName
    ) {
    }
}

