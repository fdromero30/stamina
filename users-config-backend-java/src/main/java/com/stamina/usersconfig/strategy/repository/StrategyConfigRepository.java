package com.stamina.usersconfig.strategy.repository;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.List;
import java.util.UUID;

public interface StrategyConfigRepository extends JpaRepository<StrategyConfig, UUID> {
    List<StrategyConfig> findBySymbolAndEnabledTrue(String symbol);
    
    @Query("SELECT s FROM StrategyConfig s JOIN FETCH s.user WHERE s.user.id = :userId")
    List<StrategyConfig> findByUserId(UUID userId);
}
