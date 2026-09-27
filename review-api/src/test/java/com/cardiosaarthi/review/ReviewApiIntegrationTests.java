package com.cardiosaarthi.review;

import java.net.InetSocketAddress;
import java.net.Socket;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIf;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.security.test.context.support.WithMockUser;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * End-to-end tests for the review service, against a real PostgreSQL.
 *
 * <p>Deliberately not mocked. Almost everything worth testing here lives in the
 * database -- the append-only trigger, the CHECK constraints, the views that
 * decide what a student may be graded against -- and a mocked repository would
 * test the mock.
 *
 * <p>Each test runs in a transaction that is rolled back, and every fixture uses a
 * negative {@code source_ecg_id}, so nothing can collide with a real PTB-XL
 * record even if a rollback were skipped.
 *
 * <p>The class is skipped when the development database is not running, so
 * {@code ./mvnw test} on a fresh clone reports honestly instead of failing with a
 * connection error.
 */
@SpringBootTest
@AutoConfigureMockMvc
@Transactional
@EnabledIf("databaseIsRunning")
class ReviewApiIntegrationTests {

    private static final String REVIEWER_EMAIL = "integration.reviewer@example.invalid";

    @Autowired
    private MockMvc mvc;

    @Autowired
    private JdbcClient db;

    private long reviewerId;

    static boolean databaseIsRunning() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("localhost", 55432), 500);
            return true;
        } catch (Exception exception) {
            return false;
        }
    }

    @BeforeEach
    void createReviewer() {
        reviewerId = db.sql("""
                INSERT INTO reviewers (email, full_name, role, password_hash)
                VALUES (:email, 'Integration Reviewer', 'faculty', '$2a$10$notarealhash')
                ON CONFLICT (lower(email)) DO UPDATE SET full_name = excluded.full_name
                RETURNING id
                """)
                .param("email", REVIEWER_EMAIL)
                .query(Long.class)
                .single();
    }

    // -----------------------------------------------------------------------
    // fixtures
    // -----------------------------------------------------------------------
    private long pendingCase(int ecgId, double prInterval) {
        long caseId = db.sql("""
                INSERT INTO cases (source, source_ecg_id, schema_version, engine_version, computed_at,
                                   sampling_rate, n_samples, measurement_status, overall_confidence,
                                   raw_measurement, warnings)
                VALUES ('test', :ecgId, '1.0.0', '0.1.0', now(), 500, 5000, 'NEEDS_REVIEW', 0.01,
                        '{}'::jsonb, ARRAY['p_wave_uncertain_in_2_beats'])
                RETURNING id
                """)
                .param("ecgId", ecgId)
                .query(Long.class)
                .single();

        db.sql("""
                INSERT INTO case_measurements (case_id, name, value, mad, unit, n_beats, confidence, status, flag)
                VALUES (:caseId, 'pr_interval', :pr, 6.0, 'ms', 12, 0.6, 'NEEDS_REVIEW', 'NORMAL'),
                       (:caseId, 'qt_interval', 400.0, 12.0, 'ms', 12, 0.8, 'OK', 'NORMAL')
                """)
                .param("caseId", caseId)
                .param("pr", prInterval)
                .update();

        return caseId;
    }

    // -----------------------------------------------------------------------
    // authentication
    // -----------------------------------------------------------------------
    @Test
    @DisplayName("the queue is not readable without credentials")
    void queueRequiresAuthentication() throws Exception {
        mvc.perform(get("/api/queue")).andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("a rendered ECG is not readable without credentials")
    void imagesRequireAuthentication() throws Exception {
        // These are real patient recordings. De-identified, but not ours to leave
        // open just because they are only images.
        mvc.perform(get("/api/cases/1/image/clean")).andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("health is public so a container probe does not need a password")
    void healthIsPublic() throws Exception {
        mvc.perform(get("/actuator/health")).andExpect(status().isOk());
    }

    // -----------------------------------------------------------------------
    // reading
    // -----------------------------------------------------------------------
    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a pending case appears in the queue with the warnings that held it back")
    void pendingCaseAppearsInQueue() throws Exception {
        long caseId = pendingCase(-1001, 176.0);

        mvc.perform(get("/api/queue?order=LEAST_CONFIDENT&limit=5&status=NEEDS_REVIEW"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[?(@.caseId == %d)]".formatted(caseId)).exists())
                .andExpect(jsonPath("$.items[?(@.caseId == %d)].warnings[0]".formatted(caseId))
                        .value("p_wave_uncertain_in_2_beats"));
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("case detail carries the engine's spread and confidence, not just the number")
    void caseDetailCarriesSpreadAndConfidence() throws Exception {
        long caseId = pendingCase(-1002, 176.0);

        mvc.perform(get("/api/cases/" + caseId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reviewStatus").value("pending"))
                .andExpect(jsonPath("$.measurements[?(@.name == 'pr_interval')].value").value(176.0))
                .andExpect(jsonPath("$.measurements[?(@.name == 'pr_interval')].mad").value(6.0))
                .andExpect(jsonPath("$.measurements[?(@.name == 'pr_interval')].confidence").value(0.6));
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("an unknown case is a 404, not a 500")
    void unknownCaseIsNotFound() throws Exception {
        mvc.perform(get("/api/cases/99999999")).andExpect(status().isNotFound());
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("an unknown URL is a 404, not a 500")
    void unknownUrlIsNotFound() throws Exception {
        mvc.perform(get("/api/does-not-exist")).andExpect(status().isNotFound());
    }

    // -----------------------------------------------------------------------
    // approving
    // -----------------------------------------------------------------------
    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("approving a case records who decided and when")
    void approvalIsAttributed() throws Exception {
        long caseId = pendingCase(-1010, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"action":"APPROVE","note":"matches the tracing","durationSeconds":40}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reviewStatus").value("approved"))
                .andExpect(jsonPath("$.reviewerId").value(reviewerId));

        assertThat(caseStatus(caseId)).isEqualTo("approved");
        assertThat(reviewCount(caseId, "approve")).isEqualTo(1);
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("an approved case becomes servable and its measurements reach v_served_measurements")
    void approvedCaseBecomesServable() throws Exception {
        long caseId = pendingCase(-1011, 176.0);
        assertThat(servedCount(caseId)).as("a pending case must not be servable").isZero();

        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"action":"APPROVE"}"""))
                .andExpect(status().isOk());

        assertThat(servedCount(caseId)).isEqualTo(2);
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a second decision on the same case is refused")
    void doubleReviewIsRefused() throws Exception {
        long caseId = pendingCase(-1012, 176.0);
        String body = """
                {"action":"APPROVE"}""";

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isOk());

        // Two reviewers opened the same case. The first judgement stands rather
        // than being silently overwritten by whoever clicked last.
        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON).content(body)).andExpect(status().isConflict());
    }

    // -----------------------------------------------------------------------
    // correcting
    // -----------------------------------------------------------------------
    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a correction is recorded without overwriting what the engine measured")
    void correctionDoesNotOverwriteTheComputedValue() throws Exception {
        long caseId = pendingCase(-1020, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"action":"EDIT","durationSeconds":150,
                                 "corrections":[{"name":"pr_interval","value":196.0,
                                                 "note":"P onset earlier than the engine placed it"}]}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reviewStatus").value("approved"))
                .andExpect(jsonPath("$.correctionsRecorded[0]").value("pr_interval"));

        mvc.perform(get("/api/cases/" + caseId))
                .andExpect(jsonPath("$.measurements[?(@.name == 'pr_interval')].value").value(176.0))
                .andExpect(jsonPath("$.measurements[?(@.name == 'pr_interval')].correctedValue").value(196.0));
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("the correction feeds the agreement table with the engine's own number")
    void correctionSnapshotsTheComputedValue() throws Exception {
        long caseId = pendingCase(-1021, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT","corrections":[{"name":"pr_interval","value":196.0}]}"""))
                .andExpect(status().isOk());

        Double computed = db.sql("""
                SELECT computed_value FROM measurement_corrections
                WHERE case_id = :caseId AND name = 'pr_interval'
                """)
                .param("caseId", caseId)
                .query(Double.class)
                .single();

        // Snapshotted, not joined for later: if the engine is improved and this
        // case re-measured, the row still records what the reviewer disagreed with.
        assertThat(computed).isEqualTo(176.0);
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a correction equal to the computed value writes nothing and says so")
    void unchangedCorrectionIsReportedNotStored() throws Exception {
        long caseId = pendingCase(-1022, 176.0);

        // A zero-difference row would dilute the measurement-agreement figures
        // with disagreements that never happened.
        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"action":"EDIT","corrections":[{"name":"pr_interval","value":176.0}]}"""))
                .andExpect(status().isUnprocessableContent());

        assertThat(correctionCount(caseId)).isZero();
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a physiologically impossible correction is refused with the range that would be accepted")
    void implausibleCorrectionIsRefused() throws Exception {
        long caseId = pendingCase(-1023, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"action":"EDIT","corrections":[{"name":"qt_interval","value":4000.0}]}"""))
                .andExpect(status().isUnprocessableContent())
                .andExpect(jsonPath("$.message").value(
                        org.hamcrest.Matchers.containsString("150 to 800 ms")));

        assertThat(caseStatus(caseId)).as("a refused review must not change the case").isEqualTo("pending");
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("an abnormal but possible correction is accepted")
    void abnormalCorrectionIsAccepted() throws Exception {
        long caseId = pendingCase(-1024, 176.0);

        // 280 ms is first-degree AV block, which is the entire point of the case.
        // Bounds exist to catch slipped decimal points, not abnormal findings.
        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT","corrections":[{"name":"pr_interval","value":280.0}]}"""))
                .andExpect(status().isOk());
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a correction to a measure the case does not have is refused")
    void correctionToUnknownMeasureIsRefused() throws Exception {
        long caseId = pendingCase(-1025, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT","corrections":[{"name":"left_atrial_pressure","value":12.0}]}"""))
                .andExpect(status().isUnprocessableContent());
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("the same measure cannot be corrected twice in one request")
    void duplicateCorrectionIsRefused() throws Exception {
        long caseId = pendingCase(-1026, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT","corrections":[{"name":"pr_interval","value":190.0},
                                                        {"name":"pr_interval","value":200.0}]}"""))
                .andExpect(status().isUnprocessableContent());
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("APPROVE carrying corrections is refused rather than quietly dropping them")
    void approveWithCorrectionsIsRefused() throws Exception {
        long caseId = pendingCase(-1027, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"APPROVE","corrections":[{"name":"pr_interval","value":190.0}]}"""))
                .andExpect(status().isUnprocessableContent());

        assertThat(correctionCount(caseId)).isZero();
        assertThat(caseStatus(caseId)).isEqualTo("pending");
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("EDIT with no corrections is refused")
    void editWithoutCorrectionsIsRefused() throws Exception {
        long caseId = pendingCase(-1028, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT"}"""))
                .andExpect(status().isUnprocessableContent());
    }

    // -----------------------------------------------------------------------
    // rejecting
    // -----------------------------------------------------------------------
    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a rejection without a reason is refused")
    void rejectionNeedsAReason() throws Exception {
        long caseId = pendingCase(-1030, 176.0);

        // The rejection log is reported as a pipeline-accuracy measure, and a
        // rejection with no reason is just a missing case.
        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"REJECT"}"""))
                .andExpect(status().isUnprocessableContent());

        assertThat(caseStatus(caseId)).isEqualTo("pending");
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a rejection with a reason is recorded and the case is not servable")
    void rejectionIsRecorded() throws Exception {
        long caseId = pendingCase(-1031, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"action":"REJECT","rejectionReason":"POOR_SIGNAL_QUALITY",
                                 "note":"baseline wander across the precordial leads"}"""))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.reviewStatus").value("rejected"));

        assertThat(caseStatus(caseId)).isEqualTo("rejected");
        assertThat(servedCount(caseId)).as("a rejected case must never be servable").isZero();
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a rejection reason on a non-rejection is refused")
    void rejectionReasonOnApprovalIsRefused() throws Exception {
        long caseId = pendingCase(-1032, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"APPROVE","rejectionReason":"OTHER"}"""))
                .andExpect(status().isUnprocessableContent());
    }

    // -----------------------------------------------------------------------
    // malformed requests
    // -----------------------------------------------------------------------
    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a misspelled action is the client's error, reported as 400")
    void misspelledActionIsBadRequest() throws Exception {
        long caseId = pendingCase(-1040, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"APROVE"}"""))
                .andExpect(status().isBadRequest());
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a missing action is a validation failure naming the field")
    void missingActionNamesTheField() throws Exception {
        long caseId = pendingCase(-1041, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"note":"forgot the action"}"""))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.fieldErrors.action").exists());
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("a negative duration is refused")
    void negativeDurationIsRefused() throws Exception {
        long caseId = pendingCase(-1042, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"APPROVE","durationSeconds":-5}"""))
                .andExpect(status().isBadRequest());
    }

    // -----------------------------------------------------------------------
    // bank and statistics
    // -----------------------------------------------------------------------
    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("the conditions PTB-XL cannot supply are reported rather than hidden")
    void unavailableConditionsAreVisible() throws Exception {
        mvc.perform(get("/api/conditions"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[?(@.code == 'ventricular_tachycardia')].available").value(false))
                .andExpect(jsonPath("$[?(@.code == 'ventricular_tachycardia')].candidates").value(0))
                .andExpect(jsonPath("$[?(@.code == 'hyperkalaemia')].available").value(false));
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("statistics report bias separately from scatter")
    void agreementSeparatesBiasFromScatter() throws Exception {
        // One correction of +20 ms and one of -20 ms: 20 ms of error, zero bias.
        // A single averaged figure would report this engine as perfect.
        // v_measurement_agreement aggregates every correction in the database,
        // which is right for a report card and wrong for an assertion about two
        // specific ones. Cleared inside the test transaction, so it is rolled
        // back with everything else.
        db.sql("DELETE FROM measurement_corrections WHERE name = 'pr_interval'").update();

        long high = pendingCase(-1050, 160.0);
        long low = pendingCase(-1051, 160.0);

        mvc.perform(post("/api/cases/" + high + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT","corrections":[{"name":"pr_interval","value":180.0}]}"""))
                .andExpect(status().isOk());
        mvc.perform(post("/api/cases/" + low + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"EDIT","corrections":[{"name":"pr_interval","value":140.0}]}"""))
                .andExpect(status().isOk());

        Double mae = db.sql("SELECT mae FROM v_measurement_agreement WHERE name = 'pr_interval'")
                .query(Double.class).single();
        Double bias = db.sql("SELECT bias FROM v_measurement_agreement WHERE name = 'pr_interval'")
                .query(Double.class).single();

        assertThat(mae).isEqualTo(20.0);
        assertThat(bias).isEqualTo(0.0);
    }

    @Test
    @WithMockUser(username = REVIEWER_EMAIL)
    @DisplayName("throughput is measured, because reviewer capacity is the critical path")
    void throughputIsRecorded() throws Exception {
        long caseId = pendingCase(-1060, 176.0);

        mvc.perform(post("/api/cases/" + caseId + "/review")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                        {"action":"APPROVE","durationSeconds":95}"""))
                .andExpect(status().isOk());

        Integer duration = db.sql("SELECT duration_seconds FROM reviews WHERE case_id = :caseId")
                .param("caseId", caseId)
                .query(Integer.class)
                .single();
        assertThat(duration).isEqualTo(95);
    }

    // -----------------------------------------------------------------------
    // helpers
    // -----------------------------------------------------------------------
    private String caseStatus(long caseId) {
        return db.sql("SELECT review_status FROM cases WHERE id = :caseId")
                .param("caseId", caseId).query(String.class).single();
    }

    private int reviewCount(long caseId, String action) {
        return db.sql("SELECT count(*) FROM reviews WHERE case_id = :caseId AND action = :action")
                .param("caseId", caseId).param("action", action).query(Integer.class).single();
    }

    private int correctionCount(long caseId) {
        return db.sql("SELECT count(*) FROM measurement_corrections WHERE case_id = :caseId")
                .param("caseId", caseId).query(Integer.class).single();
    }

    private int servedCount(long caseId) {
        return db.sql("SELECT count(*) FROM v_served_measurements WHERE case_id = :caseId")
                .param("caseId", caseId).query(Integer.class).single();
    }
}
