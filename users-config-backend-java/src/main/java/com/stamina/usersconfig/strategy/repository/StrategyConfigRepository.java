package com.stamina.usersconfig.strategy.repository;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface StrategyConfigRepository extends JpaRepository<StrategyConfig, UUID> {
    List<StrategyConfig> findBySymbolAndEnabledTrue(String symbol);
    List<StrategyConfig> findByUserId(UUID userId);
}