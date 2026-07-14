package com.stamina.usersconfig.strategy.entity;

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

import java.math.BigDecimal;
import java.time.LocalTime;
import java.util.UUID;

@Entity
@Table(name = "strategy_configs")
public class StrategyConfig {

    @Id
    @GeneratedValue(strategy = GenerationType.UUID)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false)
    private AppUser user;

    @Column(nullable = false)
    private String name;

    @Column(nullable = false)
    private String symbol;

    @Column(nullable = false)
    private BigDecimal maxPositionSize;

    @Column(nullable = false)
    private boolean enabled = false;

    // ---------- Risk Management ----------

    @Column
    private BigDecimal maxDrawdown;

    @Column
    private BigDecimal maxRiskPerTrade;

    @Column
    private BigDecimal maxDailyLoss;

    @Column
    private Integer maxOpenPositions;

    // ---------- Trade Parameters ----------

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "stop_loss_type_id")
    private StopLossType stopLossType;

    @Column
    private BigDecimal stopLoss;

    @Column
    private BigDecimal takeProfit;

    @Column
    private BigDecimal spreadThreshold;

    // ---------- Time & Execution ----------

    @Column
    private LocalTime tradingWindowStart;

    @Column
    private LocalTime tradingWindowEnd;

    @Column
    private BigDecimal trailingStopActivation;

    @Column
    private BigDecimal breakEvenTrigger;

    // ---------- ML Strategy ----------

    @Column(nullable = false)
    private boolean useML = false;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "ml_strategy_id")
    private MLStrategy mlStrategy;

    public StrategyConfig() {
    }

    public StrategyConfig(AppUser user, String name, String symbol, BigDecimal maxPositionSize, boolean enabled) {
        this.user = user;
        this.name = name;
        this.symbol = symbol;
        this.maxPositionSize = maxPositionSize;
        this.enabled = enabled;
    }

    // ---------- Getters & Setters ----------

    public UUID getId() {
        return id;
    }

    public AppUser getUser() {
        return user;
    }

    public void setUser(AppUser user) {
        this.user = user;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSymbol() {
        return symbol;
    }

    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }

    public BigDecimal getMaxPositionSize() {
        return maxPositionSize;
    }

    public void setMaxPositionSize(BigDecimal maxPositionSize) {
        this.maxPositionSize = maxPositionSize;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public BigDecimal getMaxDrawdown() {
        return maxDrawdown;
    }

    public void setMaxDrawdown(BigDecimal maxDrawdown) {
        this.maxDrawdown = maxDrawdown;
    }

    public BigDecimal getMaxRiskPerTrade() {
        return maxRiskPerTrade;
    }

    public void setMaxRiskPerTrade(BigDecimal maxRiskPerTrade) {
        this.maxRiskPerTrade = maxRiskPerTrade;
    }

    public BigDecimal getMaxDailyLoss() {
        return maxDailyLoss;
    }

    public void setMaxDailyLoss(BigDecimal maxDailyLoss) {
        this.maxDailyLoss = maxDailyLoss;
    }

    public Integer getMaxOpenPositions() {
        return maxOpenPositions;
    }

    public void setMaxOpenPositions(Integer maxOpenPositions) {
        this.maxOpenPositions = maxOpenPositions;
    }

    public StopLossType getStopLossType() {
        return stopLossType;
    }

    public void setStopLossType(StopLossType stopLossType) {
        this.stopLossType = stopLossType;
    }

    public BigDecimal getStopLoss() {
        return stopLoss;
    }

    public void setStopLoss(BigDecimal stopLoss) {
        this.stopLoss = stopLoss;
    }

    public BigDecimal getTakeProfit() {
        return takeProfit;
    }

    public void setTakeProfit(BigDecimal takeProfit) {
        this.takeProfit = takeProfit;
    }

    public BigDecimal getSpreadThreshold() {
        return spreadThreshold;
    }

    public void setSpreadThreshold(BigDecimal spreadThreshold) {
        this.spreadThreshold = spreadThreshold;
    }

    public LocalTime getTradingWindowStart() {
        return tradingWindowStart;
    }

    public void setTradingWindowStart(LocalTime tradingWindowStart) {
        this.tradingWindowStart = tradingWindowStart;
    }

    public LocalTime getTradingWindowEnd() {
        return tradingWindowEnd;
    }

    public void setTradingWindowEnd(LocalTime tradingWindowEnd) {
        this.tradingWindowEnd = tradingWindowEnd;
    }

    public BigDecimal getTrailingStopActivation() {
        return trailingStopActivation;
    }

    public void setTrailingStopActivation(BigDecimal trailingStopActivation) {
        this.trailingStopActivation = trailingStopActivation;
    }

    public BigDecimal getBreakEvenTrigger() {
        return breakEvenTrigger;
    }

    public void setBreakEvenTrigger(BigDecimal breakEvenTrigger) {
        this.breakEvenTrigger = breakEvenTrigger;
    }

    public boolean isUseML() {
        return useML;
    }

    public void setUseML(boolean useML) {
        this.useML = useML;
    }

    public MLStrategy getMlStrategy() {
        return mlStrategy;
    }

    public void setMlStrategy(MLStrategy mlStrategy) {
        this.mlStrategy = mlStrategy;
    }
}