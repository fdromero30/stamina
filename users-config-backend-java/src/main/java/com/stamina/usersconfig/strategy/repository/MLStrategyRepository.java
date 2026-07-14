package com.stamina.usersconfig.strategy.repository;

import com.stamina.usersconfig.strategy.entity.MLStrategy;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface MLStrategyRepository extends JpaRepository<MLStrategy, UUID> {
}