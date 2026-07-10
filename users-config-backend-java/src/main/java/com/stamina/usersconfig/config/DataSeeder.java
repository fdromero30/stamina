package com.stamina.usersconfig.config;

import com.stamina.usersconfig.strategy.entity.StrategyConfig;
import com.stamina.usersconfig.strategy.repository.StrategyConfigRepository;
import com.stamina.usersconfig.user.entity.AppUser;
import com.stamina.usersconfig.user.repository.AppUserRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.util.List;

@Component
public class DataSeeder implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);

    private final AppUserRepository userRepository;
    private final StrategyConfigRepository strategyRepository;
    private final PasswordEncoder passwordEncoder;

    public DataSeeder(AppUserRepository userRepository, StrategyConfigRepository strategyRepository, PasswordEncoder passwordEncoder) {
        this.userRepository = userRepository;
        this.strategyRepository = strategyRepository;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(String... args) {
        if (userRepository.count() > 0) {
            log.info("Database already contains data — skipping seed.");
            return;
        }

        log.info("Seeding database with initial data…");

        String defaultPassword = passwordEncoder.encode("stamina123");
        AppUser alice = userRepository.save(new AppUser("alice@stamina.local", "Alice Montenegro", defaultPassword));
        AppUser bob = userRepository.save(new AppUser("bob@stamina.local", "Bob Carter", defaultPassword));

        List.of(
                new StrategyConfig(alice, "Momentum BTC", "BTCUSDT", new BigDecimal("0.50"), true),
                new StrategyConfig(alice, "ETH Mean Reversion", "ETHUSDT", new BigDecimal("0.30"), true),
                new StrategyConfig(bob, "Index Hedge", "SPX500", new BigDecimal("1.00"), false)
        ).forEach(strategyRepository::save);

        log.info("Seeded {} users and {} strategies.", 2, 3);
    }

}