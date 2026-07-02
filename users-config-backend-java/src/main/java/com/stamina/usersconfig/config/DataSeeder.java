package com.stamina.usersconfig.config;

import com.stamina.usersconfig.strategy.StrategyConfig;
import com.stamina.usersconfig.strategy.StrategyConfigRepository;
import com.stamina.usersconfig.user.AppUser;
import com.stamina.usersconfig.user.AppUserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.List;

@Component
public class DataSeeder implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    private final AppUserRepository userRepository;
    private final StrategyConfigRepository strategyRepository;

    public DataSeeder(AppUserRepository userRepository, StrategyConfigRepository strategyRepository) {
        this.userRepository = userRepository;
        this.strategyRepository = strategyRepository;
    }

    @Override
    public void run(String... args) {
        if (userRepository.count() > 0) {
            log.info("Database already contains data — skipping seed.");
            return;
        }

        log.info("Seeding database with initial data…");

        AppUser alice = new AppUser();
        alice.setEmail("alice@stamina.local");
        alice.setDisplayName("Alice Montenegro");
        userRepository.save(alice);

        AppUser bob = new AppUser();
        bob.setEmail("bob@stamina.local");
        bob.setDisplayName("Bob Carter");
        userRepository.save(bob);

        List.of(
                createStrategy(alice, "Momentum BTC", "BTCUSDT", new BigDecimal("0.50"), true),
                createStrategy(alice, "ETH Mean Reversion", "ETHUSDT", new BigDecimal("0.30"), true),
                createStrategy(bob, "Index Hedge", "SPX500", new BigDecimal("1.00"), false)
        ).forEach(strategyRepository::save);

        log.info("Seeded {} users and {} strategies.", 2, 3);
    }

    private StrategyConfig createStrategy(AppUser user, String name, String symbol, BigDecimal maxPosition, boolean enabled) {
        StrategyConfig s = new StrategyConfig();
        s.setUser(user);
        s.setName(name);
        s.setSymbol(symbol);
        s.setMaxPositionSize(maxPosition);
        s.setEnabled(enabled);
        return s;
    }
}