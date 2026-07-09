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

        String encryptedPublic = cryptoService.encrypt(request.publicKey());
        String encryptedPrivate = cryptoService.encrypt(request.privateKey());

        ApiKey entity = new ApiKey(user, request.label(), request.broker(), encryptedPublic, encryptedPrivate);
        ApiKey saved = apiKeyRepository.save(entity);
        return toResponse(saved, request.publicKey(), request.privateKey());
    }

    @Transactional(readOnly = true)
    public List<ApiKeyResponse> listByUser(UUID userId) {
        return apiKeyRepository.findByUserId(userId)
                .stream()
                .map(entity -> {
                    String publicPlain = cryptoService.decrypt(entity.getEncryptedPublicKey());
                    String privatePlain = cryptoService.decrypt(entity.getEncryptedPrivateKey());
                    return toResponse(entity, publicPlain, privatePlain);
                })
                .toList();
    }

    private ApiKeyResponse toResponse(ApiKey entity, String publicPlain, String privatePlain) {
        String maskedPublic = mask(publicPlain);
        String maskedPrivate = mask(privatePlain);
        String combinedMasked = maskedPublic + " / " + maskedPrivate;
        return new ApiKeyResponse(
            entity.getId(),
            entity.getLabel(),
            entity.getBroker(),
            combinedMasked,
            entity.getCreatedAt()
        );
    }

    private String mask(String key) {
        if (key == null || key.isBlank()) {
            return "****";
        }
        if (key.length() <= 8) {
            return key.substring(0, Math.min(key.length(), 1)) + "****";
        }
        return key.substring(0, 4) + "****" + key.substring(key.length() - 4);
    }

    @Transactional(readOnly = true)
    public RevealedKeyResponse reveal(UUID apiKeyId, UUID userId) {
        ApiKey entity = apiKeyRepository.findById(apiKeyId)
                .orElseThrow(() -> new IllegalArgumentException("API key not found: " + apiKeyId));

        if (!entity.getUser().getId().equals(userId)) {
            throw new IllegalArgumentException("API key does not belong to this user");
        }

        String publicPlain = cryptoService.decrypt(entity.getEncryptedPublicKey());
        String privatePlain = cryptoService.decrypt(entity.getEncryptedPrivateKey());
        return new RevealedKeyResponse(publicPlain + "|" + privatePlain);
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