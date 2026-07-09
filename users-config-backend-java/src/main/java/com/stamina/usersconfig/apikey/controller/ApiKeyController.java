package com.stamina.usersconfig.apikey.controller;

import com.stamina.usersconfig.apikey.dto.ApiKeyResponse;
import com.stamina.usersconfig.apikey.dto.CreateApiKeyRequest;
import com.stamina.usersconfig.apikey.dto.RevealedKeyResponse;
import com.stamina.usersconfig.apikey.service.ApiKeyService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api-keys")
public class ApiKeyController {

    private final ApiKeyService apiKeyService;

    public ApiKeyController(ApiKeyService apiKeyService) {
        this.apiKeyService = apiKeyService;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    ApiKeyResponse create(@Valid @RequestBody CreateApiKeyRequest request) {
        return apiKeyService.create(request);
    }

    @GetMapping
    List<ApiKeyResponse> listByUser(@RequestParam("userId") UUID userId) {
        return apiKeyService.listByUser(userId);
    }

    @PostMapping("/{id}/reveal")
    RevealedKeyResponse reveal(@PathVariable("id") UUID id, @RequestParam("userId") UUID userId) {
        return apiKeyService.reveal(id, userId);
    }

    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    void delete(@PathVariable("id") UUID id, @RequestParam("userId") UUID userId) {
        apiKeyService.delete(id, userId);
    }
}