package com.stamina.usersconfig.apikey.entity;

import com.stamina.usersconfig.user.entity.AppUser;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "api_keys")
public class ApiKey {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private AppUser user;

    @Column(nullable = false)
    private String label;

    @Column(nullable = false)
    private String broker;

    @Column(nullable = false, length = 1024)
    private String encryptedKey;

    @Column(nullable = false)
    private Instant createdAt = Instant.now();

    public ApiKey() {
    }

    public ApiKey(AppUser user, String label, String broker, String encryptedKey) {
        this.user = user;
        this.label = label;
        this.broker = broker;
        this.encryptedKey = encryptedKey;
    }

    public UUID getId() {
        return id;
    }

    public AppUser getUser() {
        return user;
    }

    public String getLabel() {
        return label;
    }

    public void setLabel(String label) {
        this.label = label;
    }

    public String getBroker() {
        return broker;
    }

    public void setBroker(String broker) {
        this.broker = broker;
    }

    public String getEncryptedKey() {
        return encryptedKey;
    }

    public void setEncryptedKey(String encryptedKey) {
        this.encryptedKey = encryptedKey;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}