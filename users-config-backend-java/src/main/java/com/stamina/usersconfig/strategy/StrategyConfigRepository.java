package com.stamina.usersconfig.strategy;

import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface StrategyConfigRepository extends JpaRepository<StrategyConfig, UUID> {
}

