package com.stamina.usersconfig.strategy;

import com.stamina.usersconfig.user.AppUser;
import com.stamina.usersconfig.user.AppUserRepository;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/strategies")
public class StrategyConfigController {
    private final StrategyConfigRepository strategyRepository;
    private final AppUserRepository userRepository;

    public StrategyConfigController(
        StrategyConfigRepository strategyRepository,
        AppUserRepository userRepository
    ) {
        this.strategyRepository = strategyRepository;
        this.userRepository = userRepository;
    }

    @GetMapping
    List<StrategyConfig> list() {
        return strategyRepository.findAll();
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    StrategyConfig create(@Valid @RequestBody CreateStrategyRequest request) {
        AppUser user = userRepository.findById(request.userId())
            .orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User not found"));

        StrategyConfig strategy = new StrategyConfig();
        strategy.setUser(user);
        strategy.setName(request.name());
        strategy.setSymbol(request.symbol());
        strategy.setMaxPositionSize(request.maxPositionSize());
        strategy.setEnabled(request.enabled());
        return strategyRepository.save(strategy);
    }

    record CreateStrategyRequest(
        @NotNull UUID userId,
        @NotBlank String name,
        @NotBlank String symbol,
        @DecimalMin("0.01") BigDecimal maxPositionSize,
        boolean enabled
    ) {
    }
}

