package com.stamina.usersconfig.apikey.service;

import com.stamina.usersconfig.apikey.dto.ApiKeyResponse;
import com.stamina.usersconfig.apikey.dto.CreateApiKeyRequest;
import com.stamina.usersconfig.apikey.dto.RevealedKeyResponse;
import com.stamina.usersconfig.apikey.entity.ApiKey;
import com.stamina.usersconfig.apikey.repository.ApiKeyRepository;
import com.stamina.usersconfig.config.CryptoService;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
public class ApiKeyService {

    private final ApiKeyRepository apiKeyRepository;
    private final AppUserRepository userRepository;
    private final CryptoService cryptoService;

    public ApiKeyService(ApiKeyRepository apiKeyRepository,
                         AppUserRepository userRepository,
                         CryptoService cryptoService) {
        this.apiKeyRepository = apiKeyRepository;
        this.userRepository = userRepository;
        this.cryptoService = cryptoService;
    }

    @Transactional
    public ApiKeyResponse create(CreateApiKeyRequest request) {
        AppUser user = userRepository.findById(UUID.fromString(request.userId()))
                .orElseThrow(() -> new IllegalArgumentException("User not found: " + request.userId()));

        String encrypted = cryptoService.encrypt(request.apiKey());

        ApiKey entity = new ApiKey(user, request.label(), request.broker(), encrypted);
        ApiKey saved = apiKeyRepository.save(entity);
        return toResponse(saved, request.apiKey());
    }

    @Transactional(readOnly = true)
    public List<ApiKeyResponse> listByUser(UUID userId) {
        return apiKeyRepository.findByUserId(userId)
                .stream()
                .map(entity -> {
                    String plaintext = cryptoService.decrypt(entity.getEncryptedKey());
                    return toResponse(entity, plaintext);
                })
                .toList();
    }

    private ApiKeyResponse toResponse(ApiKey entity, String plaintextKey) {
        String masked;
        if (plaintextKey.length() <= 8) {
            masked = plaintextKey.substring(0, Math.min(plaintextKey.length(), 1)) + "****";
        } else {
            masked = plaintextKey.substring(0, 4) + "****" + plaintextKey.substring(plaintextKey.length() - 4);
        }
        return new ApiKeyResponse(
            entity.getId(),
            entity.getLabel(),
            entity.getBroker(),
            masked,
            entity.getCreatedAt()
        );
    }

    @Transactional(readOnly = true)
    public RevealedKeyResponse reveal(UUID apiKeyId, UUID userId) {
        ApiKey entity = apiKeyRepository.findById(apiKeyId)
                .orElseThrow(() -> new IllegalArgumentException("API key not found: " + apiKeyId));

        if (!entity.getUser().getId().equals(userId)) {
            throw new IllegalArgumentException("API key does not belong to this user");
        }

        String plaintext = cryptoService.decrypt(entity.getEncryptedKey());
        return new RevealedKeyResponse(plaintext);
    }

    @Transactional
    public void delete(UUID apiKeyId, UUID userId) {
        ApiKey entity = apiKeyRepository.findById(apiKeyId)
                .orElseThrow(() -> new IllegalArgumentException("API key not found: " + apiKeyId));

        if (!entity.getUser().getId().equals(userId)) {
            throw new IllegalArgumentException("API key does not belong to this user");
        }

        apiKeyRepository.delete(entity);
    }
}