package com.cardiosaarthi.review.bootstrap;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * Three accounts with memorable credentials, for demonstrating the platform.
 *
 * <p>Typing a twenty-character generated password in front of a room is its own
 * small disaster, so these exist: a faculty login, a student login and a patient
 * login with short identifiers that can be read off a slide.
 *
 * <p>The faculty account carries the name of the faculty member this platform
 * was built for rather than a placeholder, because a teacher looking at a
 * dashboard headed "Demo Faculty" is being shown a mock-up, and the whole claim
 * of the review console is that a named reviewer stands behind every approved
 * case. The name is real; the mail domain is the project's own stand-in and
 * routes nowhere.
 *
 * <p>They bypass the twelve-character minimum the account endpoint enforces.
 * That minimum is not relaxed -- it still applies to every account created
 * through the API, which is where real faculty accounts come from. This is a
 * separate, deliberate path that has to be switched on, creates exactly three
 * known accounts, and says loudly in the log that it did.
 *
 * <p>Off unless {@code CARDIO_DEMO_ACCOUNTS=true}. It must stay off anywhere the
 * service is reachable from another machine: a four-digit password on a host
 * that is not localhost is not a weak password, it is an open door.
 */
@Component
public class DemoAccounts implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DemoAccounts.class);

    private static final String PASSWORD = "1234";

    @ConfigurationProperties(prefix = "cardiosaarthi.demo-accounts")
    public record Settings(boolean enabled) {
    }

    private final Settings settings;
    private final JdbcClient db;
    private final PasswordEncoder passwordEncoder;

    DemoAccounts(Settings settings, JdbcClient db, PasswordEncoder passwordEncoder) {
        this.settings = settings;
        this.db = db;
        this.passwordEncoder = passwordEncoder;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!settings.enabled()) {
            return;
        }

        String hash = passwordEncoder.encode(PASSWORD);

        db.sql("""
                INSERT INTO reviewers (email, full_name, role, college_id, password_hash)
                VALUES ('param.kolekar@terna.edu', 'Dr. Param Kolekar', 'faculty', 'TE/1234', :hash)
                ON CONFLICT (lower(email)) DO UPDATE SET
                    full_name = excluded.full_name,
                    college_id = excluded.college_id,
                    password_hash = excluded.password_hash,
                    active = true
                """)
                .param("hash", hash)
                .update();

        db.sql("""
                INSERT INTO students (email, full_name, college_id, cohort, password_hash)
                VALUES ('demo.student@terna.edu', 'Demo Student', 'TE/4321', 'demo', :hash)
                ON CONFLICT (lower(email)) DO UPDATE SET
                    college_id = excluded.college_id,
                    password_hash = excluded.password_hash,
                    active = true
                """)
                .param("hash", hash)
                .update();

        db.sql("""
                INSERT INTO patients (email, full_name, patient_ref, password_hash)
                VALUES ('demo.patient@example.invalid', 'Demo Patient', 'PT/1234', :hash)
                ON CONFLICT (lower(email)) DO UPDATE SET
                    patient_ref = excluded.patient_ref,
                    password_hash = excluded.password_hash,
                    active = true
                """)
                .param("hash", hash)
                .update();

        // A report to read. Issued against the first approved case, because an
        // unapproved one cannot be issued at all -- a trigger refuses it, for
        // the same reason an unreviewed case cannot reach a student.
        db.sql("""
                INSERT INTO patient_reports (patient_id, case_id, issued_on)
                SELECT p.id, c.id, current_date
                FROM patients p
                CROSS JOIN LATERAL (
                    SELECT id FROM cases WHERE review_status = 'approved' ORDER BY id LIMIT 1
                ) c
                WHERE p.email = 'demo.patient@example.invalid'
                ON CONFLICT (patient_id, case_id) DO NOTHING
                """)
                .update();

        // Deliberately loud. An instance running with these enabled and reachable
        // from anywhere but this machine is a problem, and the log is where
        // somebody notices.
        log.warn("DEMO ACCOUNTS ENABLED: faculty TE/1234, student TE/4321 and patient PT/1234, "
                + "all three with a four-digit password. Disable CARDIO_DEMO_ACCOUNTS "
                + "anywhere this service is not bound to localhost.");
    }
}
