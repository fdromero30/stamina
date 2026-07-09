package com.stamina.usersconfig.apikey.repository;

import com.stamina.usersconfig.apikey.entity.ApiKey;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.UUID;

public interface ApiKeyRepository extends JpaRepository<ApiKey, UUID> {
    List<ApiKey> findByUserId(UUID userId);

    @Query("SELECT ak FROM ApiKey ak JOIN FETCH ak.user WHERE ak.user.id = :userId")
    List<ApiKey> findByUserIdWithUser(@Param("userId") UUID userId);
}
