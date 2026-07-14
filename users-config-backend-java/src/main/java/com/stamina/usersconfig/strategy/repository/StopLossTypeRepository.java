package com.stamina.usersconfig.strategy.repository;

import com.stamina.usersconfig.strategy.entity.StopLossType;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface StopLossTypeRepository extends JpaRepository<StopLossType, UUID> {
}