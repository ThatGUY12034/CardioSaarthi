package com.cardiosaarthi.review.patient;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.List;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;

import com.cardiosaarthi.review.error.NotFoundException;

/**
 * A patient's own report, explained.
 *
 * <p>The patient is the one reader of this platform who cannot check what they
 * are told. A student can look at the trace; a reviewer can look at the
 * measurement; a patient has neither the training nor the data. Everything here
 * follows from that.
 *
 * <p>So no sentence is composed. Each one is selected by the computed finding
 * from a table of sentences a clinician has approved, and a finding with no
 * approved sentence is simply not explained rather than explained by something
 * written on the spot. The platform would rather say less than say something
 * nobody signed off.
 *
 * <p>And nothing here is a diagnosis. The sentences say what the recording
 * showed and refer the patient to their clinician for what it means; a database
 * constraint rejects any sentence that reaches for diagnostic language.
 */
@Service
public class PatientService {

    private final JdbcClient db;

    PatientService(JdbcClient db) {
        this.db = db;
    }

    // -----------------------------------------------------------------------
    // shapes
    // -----------------------------------------------------------------------
    public record ReportSummary(long reportId, long caseId, LocalDate issuedOn,
                                String clinicianNote) {
    }

    /** One finding, in the patient's language. */
    public record Explained(int step, String label, String measured, String headline,
                            String plainText, boolean reassuring, boolean explained) {
    }

    public record Report(long reportId, long caseId, LocalDate issuedOn, String clinicianNote,
                         List<Explained> findings, int explainedCount, int totalFindings,
                         boolean clinicianApproved) {
    }

    public record GlossaryEntry(String term, String plainText, boolean approved) {
    }

    // -----------------------------------------------------------------------
    // reads
    // -----------------------------------------------------------------------
    public List<ReportSummary> reportsFor(long patientId) {
        return db.sql("""
                SELECT DISTINCT r.id, r.case_id, r.issued_on, r.clinician_note
                FROM patient_reports r
                JOIN cases c ON c.id = r.case_id AND c.review_status = 'approved'
                WHERE r.patient_id = :patientId
                ORDER BY r.issued_on DESC, r.id DESC
                """)
                .param("patientId", patientId)
                .query((rs, n) -> new ReportSummary(
                        rs.getLong("id"), rs.getLong("case_id"),
                        rs.getObject("issued_on", LocalDate.class),
                        rs.getString("clinician_note")))
                .list();
    }

    /** A measured value as the patient's own report holds it. */
    private record Finding(int step, String concept, String label, Double value,
                           String textValue, String unit, String status) {
    }

    public Report report(long patientId, long reportId) {
        List<Finding> findings = db.sql("""
                SELECT step, concept, label, value, text_value, unit, status
                FROM v_patient_report_values
                WHERE report_id = :reportId AND patient_id = :patientId
                ORDER BY step
                """)
                .param("reportId", reportId)
                .param("patientId", patientId)
                .query((rs, n) -> new Finding(
                        rs.getInt("step"), rs.getString("concept"), rs.getString("label"),
                        rs.getObject("value") == null ? null : rs.getDouble("value"),
                        rs.getString("text_value"), rs.getString("unit"), rs.getString("status")))
                .list();

        if (findings.isEmpty()) {
            // Either no such report, or it belongs to somebody else. A patient
            // has no business learning that another patient's report exists.
            throw new NotFoundException("no report " + reportId);
        }

        ReportSummary summary = reportsFor(patientId).stream()
                .filter(r -> r.reportId() == reportId)
                .findFirst()
                .orElseThrow(() -> new NotFoundException("no report " + reportId));

        List<Explained> explained = new ArrayList<>();
        int withSentence = 0;
        for (Finding finding : findings) {
            String band = bandFor(finding);
            Sentence sentence = band == null ? null : sentenceFor(finding.concept(), band);
            String measured = measuredText(finding);

            if (sentence == null) {
                // Named, not explained. Leaving the row out entirely would hide
                // from the patient that the recording contains something nobody
                // has written an approved sentence for.
                explained.add(new Explained(finding.step(), finding.label(), measured,
                        null, null, false, false));
                continue;
            }
            withSentence++;
            explained.add(new Explained(finding.step(), finding.label(), measured,
                    sentence.headline(), sentence.plainText(), sentence.reassuring(), true));
        }

        return new Report(summary.reportId(), summary.caseId(), summary.issuedOn(),
                summary.clinicianNote(), explained, withSentence, explained.size(),
                clinicianApproved());
    }

    public List<GlossaryEntry> glossary() {
        return db.sql("SELECT term, plain_text, approved FROM glossary_terms ORDER BY term")
                .query((rs, n) -> new GlossaryEntry(
                        rs.getString("term"), rs.getString("plain_text"), rs.getBoolean("approved")))
                .list();
    }

    // -----------------------------------------------------------------------
    // selection
    // -----------------------------------------------------------------------
    private record Sentence(String headline, String plainText, boolean reassuring) {
    }

    /**
     * Only approved sentences are ever returned.
     *
     * <p>Unlike the student runtime, there is no draft fallback here. A student
     * shown a draft explanation is told it is a draft and can weigh it; a
     * patient cannot, so a sentence awaiting approval is simply not shown.
     */
    private Sentence sentenceFor(String concept, String finding) {
        return db.sql("""
                SELECT headline, plain_text, reassuring
                FROM patient_explanations
                WHERE concept = :concept AND finding = :finding AND approved
                """)
                .param("concept", concept)
                .param("finding", finding)
                .query((rs, n) -> new Sentence(
                        rs.getString("headline"), rs.getString("plain_text"),
                        rs.getBoolean("reassuring")))
                .optional()
                .orElse(null);
    }

    /**
     * Whether a clinician, rather than the seed account, approved this wording.
     *
     * <p>A seeded approval is not a clinical approval, and the page says which
     * it is showing. The same distinction the case bank draws between the
     * `system` reviewer and a named one.
     */
    private boolean clinicianApproved() {
        return db.sql("""
                SELECT total > 0 AND approved_by_clinician = total
                FROM v_patient_explanation_provenance
                """)
                .query(Boolean.class)
                .single();
    }

    /**
     * Which band of the measurement this is.
     *
     * <p>The thresholds are the ones the engine already uses, held here only to
     * choose a sentence. They decide which approved paragraph is shown, never
     * what the measurement was.
     */
    static String bandFor(Finding finding) {
        if ("NOT_MEASURABLE".equals(finding.status())) {
            return null;
        }
        if (finding.textValue() != null && !finding.textValue().isBlank()) {
            return finding.textValue().trim().toUpperCase();
        }
        if (finding.value() == null) {
            return null;
        }
        double value = finding.value();
        return switch (finding.concept()) {
            case "rate" -> value < 60 ? "LOW" : value > 100 ? "HIGH" : "NORMAL";
            case "qrs" -> value > 120 ? "WIDE" : "NORMAL";
            default -> null;
        };
    }

    private static String measuredText(Finding finding) {
        if ("NOT_MEASURABLE".equals(finding.status())) {
            return "not measurable on this recording";
        }
        if (finding.textValue() != null && !finding.textValue().isBlank()) {
            return finding.textValue().toLowerCase().replace('_', ' ');
        }
        if (finding.value() == null) {
            return "not reported";
        }
        String unit = finding.unit() == null ? "" : " " + finding.unit();
        return "%.0f%s".formatted(finding.value(), unit);
    }
}
