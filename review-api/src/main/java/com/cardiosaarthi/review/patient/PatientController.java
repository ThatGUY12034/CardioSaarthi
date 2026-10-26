package com.cardiosaarthi.review.patient;

import java.util.List;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.oauth2.server.resource.authentication.JwtAuthenticationToken;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.cardiosaarthi.review.error.NotFoundException;

/**
 * Layer 4: what a patient may read about their own recording.
 *
 * <p>Every endpoint is scoped to the caller and nothing takes a patient id from
 * the request. A patient identifier a caller can choose is a patient identifier
 * a caller can choose to be somebody else's, and of all the data in this
 * platform this is the data where that matters most.
 */
@RestController
@RequestMapping("/api/patient")
@PreAuthorize("hasRole('PATIENT')")
public class PatientController {

    private final PatientService patients;
    private final JdbcClient db;

    PatientController(PatientService patients, JdbcClient db) {
        this.patients = patients;
        this.db = db;
    }

    @GetMapping("/reports")
    public List<PatientService.ReportSummary> reports() {
        return patients.reportsFor(currentPatientId());
    }

    @GetMapping("/reports/{id}")
    public PatientService.Report report(@PathVariable long id) {
        return patients.report(currentPatientId(), id);
    }

    @GetMapping("/glossary")
    public List<PatientService.GlossaryEntry> glossary() {
        return patients.glossary();
    }

    /**
     * The patient making this request, from the token or the Basic principal.
     *
     * <p>Not shared with {@link com.cardiosaarthi.review.study.CurrentStudent}
     * on purpose: resolving "the current person" against whichever table happens
     * to match is how a student ends up reading a patient's report.
     */
    private long currentPatientId() {
        Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
        if (authentication == null || !authentication.isAuthenticated()) {
            throw new IllegalStateException("no authenticated patient on this request");
        }
        if (authentication instanceof JwtAuthenticationToken token) {
            Long id = token.getToken().getClaim("uid");
            if (id == null) {
                throw new IllegalStateException("token carries no uid claim");
            }
            return id;
        }
        return db.sql("SELECT id FROM patients WHERE lower(email) = lower(:email) AND active")
                .param("email", authentication.getName())
                .query(Long.class)
                .optional()
                .orElseThrow(() -> new NotFoundException(
                        "authenticated as " + authentication.getName() + " but no patient row exists"));
    }
}
