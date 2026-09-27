package com.cardiosaarthi.review.bootstrap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.ApplicationArguments;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import com.cardiosaarthi.review.config.ApiProperties;
import com.cardiosaarthi.review.reviewer.ReviewerRepository;

/**
 * Creates one administrator at start up, if configured.
 *
 * <p>This exists for one reason: a freshly installed service has no accounts, and
 * nothing can be logged into to create the first one. It is not a way to manage
 * faculty accounts, and it does nothing at all unless an email and password are
 * configured -- which is the right default for a service nobody has set up yet.
 *
 * <p>The password is read from configuration and hashed before it touches the
 * database. It is never logged.
 */
@Component
public class ReviewerBootstrap implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(ReviewerBootstrap.class);

    private final ApiProperties properties;
    private final ReviewerRepository reviewers;
    private final PasswordEncoder passwordEncoder;

    ReviewerBootstrap(ApiProperties properties, ReviewerRepository reviewers, PasswordEncoder passwordEncoder) {
        this.properties = properties;
        this.reviewers = reviewers;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(ApplicationArguments args) {
        ApiProperties.Bootstrap bootstrap = properties.bootstrap();

        if (bootstrap == null || !bootstrap.isConfigured()) {
            log.info("no bootstrap reviewer configured; set CARDIO_BOOTSTRAP_EMAIL and "
                    + "CARDIO_BOOTSTRAP_PASSWORD in .env if nothing can log in yet");
            return;
        }

        String name = bootstrap.fullName() == null || bootstrap.fullName().isBlank()
                ? bootstrap.email()
                : bootstrap.fullName();

        long id = reviewers.upsert(bootstrap.email(), name, "admin", passwordEncoder.encode(bootstrap.password()));
        log.info("bootstrap administrator ready: reviewer {} <{}>", id, bootstrap.email());
    }
}
