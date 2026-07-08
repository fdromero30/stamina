package com.stamina.usersconfig.strategy.service;

import com.stamina.usersconfig.strategy.dto.CreateStrategyRequest;
import com.stamina.usersconfig.strategy.dto.StrategyResponse;
import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import com.stamina.usersconfig.strategy.repository.StrategyConfigRepository;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

@Service
public class StrategyConfigService {

    private final StrategyConfigRepository strategyRepository;
    private final AppUserRepository userRepository;

    public StrategyConfigService(StrategyConfigRepository strategyRepository, AppUserRepository userRepository) {
        this.strategyRepository = strategyRepository;
        this.userRepository = userRepository;
    }

    @Transactional(readOnly = true)
    public List<StrategyResponse> listAll() {
        return strategyRepository.findAll()
            .stream()
            .map(StrategyResponse::fromEntity)
            .toList();
    }

    @Transactional
    public StrategyResponse create(CreateStrategyRequest request) {
        AppUser user = userRepository.findById(request.userId())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        StrategyConfig strategy = new StrategyConfig(
            user,
            request.name(),
            request.symbol(),
            request.maxPositionSize(),
            request.enabled()
        );

        StrategyConfig saved = strategyRepository.save(strategy);
        return StrategyResponse.fromEntity(saved);
    }
}