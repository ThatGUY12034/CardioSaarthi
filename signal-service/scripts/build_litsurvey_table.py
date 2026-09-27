"""Literature survey comparison table, in the standard project-report format.

Content comes from the project's own literature-review tree, with the factual
errors found in that diagram corrected -- the wrong model names in the LLM
study, the stale withheld-case count, an unsupported claim and three
typographic errors. Every correction is listed on the second sheet, so the
change is auditable rather than silent.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from openpyxl import Workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

HEADER_FILL = PatternFill("solid", fgColor="4472C4")
ROW_A = PatternFill("solid", fgColor="DCE3F4")
ROW_B = PatternFill("solid", fgColor="C7D2EA")
OURS = PatternFill("solid", fgColor="D9EAD3")

_inner = Side(style="thin", color="FFFFFF")
_edge = Side(style="thin", color="8EA9DB")
BORDER = Border(left=_inner, right=_inner, top=_inner, bottom=_inner)
OUTER = Border(left=_edge, right=_edge, top=_edge, bottom=_edge)

HEADERS = ["Sr\nNo.", "Paper (Authors)", "Key Findings", "Aspects Addressed", "Limitations"]

ROWS: list[tuple[str, str, str, str, str]] = [
    (
        "Educational Interventions to Improve ECG Interpretation Competence Among Nurses: "
        "A Systematic Review",
        "(Boyd E. et al., Nurse Education in Practice, 2026)",
        "Systematic review of 23 studies (RCTs and quasi-experimental designs) across MEDLINE, "
        "CINAHL, Embase and Scopus. Educational interventions were consistently associated with "
        "improved ECG interpretation competence. Five themes were identified, including "
        "sustainability and reinforcement of learning over time.",
        "Nursing ECG education; structured and traditional teaching; technology-enhanced "
        "learning; micro-learning; blended and learner-centred models; retention of skills",
        "No specific intervention or platform is proposed or evaluated. Heterogeneous study "
        "designs prevent any pooled estimate of effect size. Does not address measurement "
        "accuracy, automated grading, or per-student feedback.",
    ),
    (
        "Deep Learning for ECG Analysis: Benchmarks and Insights from PTB-XL",
        "(Strodthoff N., Wagner P., Schaeffter T., Samek W., IEEE JBHI, 2021)",
        "Establishes the field-standard benchmark, stratified train/test folds and evaluation "
        "protocol for ECG classification on PTB-XL, with baseline deep-learning results across "
        "the diagnostic superclasses.",
        "Diagnostic classification; reproducible benchmarking protocol; standardised evaluation "
        "on 12-lead ECG",
        "Benchmarks diagnostic classification only. Provides no interval measurement, no "
        "explanation of findings, and no learner-facing application.",
    ),
    (
        "Diagnostic Accuracy and Reliability of Multimodal Large Language Models in "
        "Electrocardiogram Interpretation",
        "(Stelling H., Kraus A., Grieb G., Breidung D., Guler I., Life, 2026)",
        "2,275 task-level assessments across five multimodal LLMs (ChatGPT-5.3, Gemini 3.1 Pro, "
        "Claude Opus 4.6, Grok 4.1, ERNIE 5.0), each ECG presented over five independent runs "
        "and compared against expert consensus. Overall categorical accuracy 52.3-64.9%. QRS "
        "duration was the strongest task (66.2-90.8%); ST/T morphology the weakest "
        "(20.0-41.5%). A dissociation between accuracy and reliability was reported.",
        "Rhythm; electrical axis; PR interval and P-wave morphology; QRS duration; ST/T "
        "morphology; QTc interval; heart-rate estimation",
        "Output is non-deterministic: the same model returns different answers on repeated "
        "presentations of the same ECG, so it cannot supply a fixed value to grade a student "
        "against. Accuracy is insufficient for clinical measurement. No retrieval grounding or "
        "external knowledge base is used.",
    ),
    (
        "PTB-XL, a Large Publicly Available Electrocardiography Dataset",
        "(Wagner P., Strodthoff N., Bousseljot R.-D. et al., Scientific Data, 2020)",
        "21,799 ten-second 12-lead records from 18,869 patients at 100 Hz and 500 Hz, with "
        "cardiologist SCP-ECG annotations, per-record signal-quality flags and a CC-BY licence. "
        "Now the reference corpus for ECG machine-learning research.",
        "Public 12-lead ECG corpus; inherited cardiologist diagnostic labels; signal-quality "
        "metadata; standardised evaluation folds",
        "Distributes signals only: contains no ECG images, so teaching material must be "
        "rendered. Diagnostically imbalanced at the tail -- ventricular tachycardia and "
        "electrolyte disturbances are absent entirely, and second- and third-degree AV block "
        "have only 14 and 16 records respectively (verified against the dataset metadata in "
        "this project).",
    ),
    (
        "Retrieval-Augmented Generation in Healthcare: A Narrative Review of Methods, "
        "Contributions and Future Directions",
        "(Digital Medicine, 12(3), 2026)",
        "Synthesises retrieval-augmented generation methods across clinical applications. "
        "Grounding model output in authoritative sources reduces hallucination and produces a "
        "transparent, citable chain back to the source material.",
        "Hallucination mitigation; source citation and auditability; guideline-grounded "
        "clinical text generation",
        "Narrative review rather than systematic. No ECG-specific RAG study was located. "
        "Addresses explanation quality only -- retrieval cannot compute a clinical measurement "
        "from a waveform.",
    ),
    (
        "PROPOSED SYSTEM -- CardioSaarthi: An AI-Based Adaptive Platform for ECG Learning and "
        "Clinical Case Simulation",
        "(This work, 2026)",
        "Deterministic measurement engine validated against LUDB (200 records) and the QT "
        "Database (101 records), neither used for tuning. Beat detection 98.7% sensitivity / "
        "98.6% PPV. Boundary error: QRS onset 13.4 ms, QRS offset 10.1 ms, P onset 11.8 ms, "
        "T offset 19.3 ms. QT median absolute error 28 ms. 714 cases measured and rendered; "
        "385 released and 327 automatically withheld by the confidence gate for faculty review.",
        "Rate; rhythm regularity; PR, QRS, QT and both QTc corrections; frontal axis; per-lead "
        "ST deviation with territorial grouping; standards-compliant rendering at 25 mm/s and "
        "10 mm/mV; nine-step guided interpretation; retrieval-grounded explanation; faculty "
        "review workflow",
        "Clinical validation with nursing faculty is pending. P-wave delineation coverage is "
        "74%, the acknowledged weak point. The educational pre-test/post-test study with the "
        "nursing cohort has not yet been conducted.",
    ),
]

NOTES: list[tuple[str, int, bool, str]] = [
    ("Corrections applied to the literature-review diagram", 13, True, "1A1A1A"),
    ("", 11, False, "1A1A1A"),
    ("Sheet 1 differs from the literature-review tree in the places listed below. Each is a "
     "correction of a factual or typographic error, not a rewrite of the argument.",
     11, False, "444444"),
    ("", 11, False, "1A1A1A"),
    ("1.  Model names (Box 3). The diagram says 'GPT-4o / Claude / Gemini'. The paper evaluated "
     "FIVE models -- ChatGPT-5.3, Gemini 3.1 Pro, Claude Opus 4.6, Grok 4.1 and ERNIE 5.0. "
     "GPT-4o was not among them.", 11, False, "1A1A1A"),
    ("2.  Withheld case count (Box 6). The diagram says 221 auto-withheld. After the QT "
     "plausibility gate and the atrial-fibrillation PR rule were added, the figures are 327 "
     "withheld and 385 released, of 714 measured.", 11, False, "1A1A1A"),
    ("3.  'Axis and BBB reads poor' (Box 3) removed. Bundle branch block was not one of the "
     "paper's six categorical tasks, so the claim is unsupported. Replaced with the verified "
     "figures: QRS duration best at 66.2-90.8%, ST/T weakest at 20.0-41.5%.", 11, False, "1A1A1A"),
    ("4.  'No measurement ground truth' (Box 4) softened. PTB-XL-Image-17K does ship "
     "ground-truth signals and segmentation masks; the accurate point is that its ground truth "
     "serves digitisation, not interval measurement.", 11, False, "1A1A1A"),
    ("5.  Typographic errors corrected: 'debiased artifacts' to deliberate artifacts; "
     "'2/3 AV black' to AV block; 'hullucination' to hallucination; 'withfield' to withheld.",
     11, False, "1A1A1A"),
    ("", 11, False, "1A1A1A"),
    ("STILL TO VERIFY BEFORE SUBMISSION", 12, True, "A3352C"),
    ("The '75.6% majority-class baseline' quoted in the diagram could not be located in the "
     "published abstract or summary of the Stelling et al. paper, so it has been left out of "
     "this table. Either cite it from the results section with a page number, or omit it -- "
     "the 52.3-64.9% accuracy range and the inter-run inconsistency carry the argument on "
     "their own.", 11, False, "1A1A1A"),
    ("", 11, False, "1A1A1A"),
    ("Citation status (checked against publisher records, 9 August 2026)", 12, True, "1A1A1A"),
    ("Row 1   Boyd E. et al. -- partly verified. The 23 studies, the four databases and the "
     "five themes are confirmed; the full author list and page numbers are paywalled.",
     11, False, "444444"),
    ("Row 2   Strodthoff et al., IEEE JBHI 25(5):1519-1528, 2021 -- high confidence. This is "
     "the project's IEEE base paper.", 11, False, "444444"),
    ("Row 3   Stelling et al., Life 16(4):681, 2026, doi 10.3390/life16040681 -- VERIFIED, "
     "including all five author names, the model list and the accuracy figures.",
     11, False, "444444"),
    ("Row 4   Wagner et al., Scientific Data 7:154, 2020 -- high confidence. The imbalance "
     "figures were measured directly from the dataset metadata in this project.",
     11, False, "444444"),
    ("Row 5   Digital Medicine 12(3), 2026, doi 10.1097/dm-2025-00015 -- VERIFIED; author list "
     "paywalled.", 11, False, "444444"),
    ("Row 6   This work. Every figure is reproducible by running "
     "'cardiosignal validate --report'.", 11, False, "444444"),
]


def build(out: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Literature Survey"
    ws.sheet_view.showGridLines = False

    for col, head in enumerate(HEADERS, start=1):
        cell = ws.cell(1, col, head)
        cell.fill = HEADER_FILL
        cell.font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        cell.border = OUTER
    ws.row_dimensions[1].height = 34

    for i, (title, authors, findings, aspects, limits) in enumerate(ROWS):
        row = i + 2
        is_ours = title.startswith("PROPOSED SYSTEM")
        fill = OURS if is_ours else (ROW_A if i % 2 == 0 else ROW_B)

        ws.cell(row, 1, i + 1)
        # Bold title, regular author line -- the convention the reference table uses.
        # b=False must be stated explicitly: left unset, the run inherits the cell
        # font and Excel renders the author line bold as well.
        ws.cell(row, 2).value = CellRichText(
            TextBlock(InlineFont(rFont="Arial", sz=11, b=True), title + " "),
            TextBlock(InlineFont(rFont="Arial", sz=11, b=False), authors),
        )
        ws.cell(row, 3, findings)
        ws.cell(row, 4, aspects)
        ws.cell(row, 5, limits)

        for col in range(1, 6):
            cell = ws.cell(row, col)
            cell.fill = fill
            cell.border = BORDER
            cell.alignment = Alignment(
                horizontal="center" if col == 1 else "left",
                vertical="center" if col == 1 else "top",
                wrap_text=True,
            )
            # Column 2 still needs a base font. A rich-text run that does not
            # state b= inherits the cell font, so leaving the cell font unset
            # let the author line render bold along with the title.
            cell.font = Font(name="Arial", size=11, bold=(col == 1))
        ws.row_dimensions[row].height = 138

    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 52
    ws.column_dimensions["D"].width = 40
    ws.column_dimensions["E"].width = 48
    ws.freeze_panes = "A2"
    ws.page_setup.orientation = "landscape"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    notes = wb.create_sheet("Corrections & Sources")
    notes.sheet_view.showGridLines = False
    for i, (text, size, bold, colour) in enumerate(NOTES, start=1):
        cell = notes.cell(i, 1, text)
        cell.font = Font(name="Arial", size=size, bold=bold, color=colour)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    notes.column_dimensions["A"].width = 118

    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    default = (
        Path(__file__).resolve().parents[2] / "docs" / "planning" / "literature_survey_table.xlsx"
    )
    parser.add_argument("--out", type=Path, default=default)
    args = parser.parse_args()
    print(f"written -> {build(args.out)}")
    print(f"written -> {render_slide_png(args.out.with_suffix('.png'))}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# Slide version
# ---------------------------------------------------------------------------
# The workbook text is written to be read at desk distance. On a 16:9 slide the
# same wording lands at roughly 8pt on a projector, which nobody reads. These
# are the same six rows cut to about 40% -- the claim in each cell is unchanged,
# only the sentences around it are gone. Both versions live in this one file so
# they cannot drift apart.
SHORT_ROWS: list[tuple[str, str, str, str, str]] = [
    (
        "Educational Interventions Review",
        "(Boyd E. et al., Nurse Educ. Pract., 2026)",
        "23 studies across 4 databases. Interventions improve competence; "
        "reinforcement over time is a named theme.",
        "Nursing ECG education; technology-enhanced and blended learning; skill retention",
        "No platform proposed. Heterogeneous designs prevent a pooled effect size.",
    ),
    (
        "PTB-XL Deep Learning Benchmark",
        "(Strodthoff N. et al., IEEE JBHI, 2021)",
        "Field-standard benchmark, stratified folds and evaluation protocol for "
        "ECG classification.",
        "Diagnostic classification; reproducible benchmarking on 12-lead ECG",
        "Classification only. No interval measurement, no explanation, no learner-facing use.",
    ),
    (
        "Multimodal LLM ECG Reliability",
        "(Stelling H. et al., Life, 2026)",
        "2,275 assessments, 5 LLMs, 5 repeat runs each. Accuracy 52.3-64.9%. "
        "ST/T weakest (20-41%); QRS duration best (66-91%).",
        "Rhythm, axis, PR, QRS duration, ST/T, QTc, heart rate",
        "Non-deterministic: different answers on repeated runs, so it cannot supply "
        "a fixed value to grade against.",
    ),
    (
        "PTB-XL Dataset",
        "(Wagner P. et al., Scientific Data, 2020)",
        "21,799 records, 18,869 patients, 12-lead, cardiologist SCP-ECG "
        "annotations, quality flags, CC-BY.",
        "Public ECG corpus; inherited diagnostic labels; signal-quality metadata",
        "Signals only, no images. VT and electrolyte disturbances absent; 2nd/3rd degree "
        "AV block only 14 and 16 records.",
    ),
    (
        "Healthcare RAG Narrative Review",
        "(Digital Medicine, 2026)",
        "Grounding output in authoritative sources reduces hallucination and gives "
        "a transparent, citable chain.",
        "Hallucination mitigation; source citation and auditability",
        "Narrative review only. No ECG-specific RAG study. Cannot compute a measurement.",
    ),
    (
        "PROPOSED SYSTEM - CardioSaarthi",
        "(This work, 2026)",
        "Validated on LUDB (200 records) + QTDB (101). Detection 98.7% Se / 98.6% PPV. "
        "QRS onset 13.4 ms, P onset 11.8 ms MAE.",
        "Rate, rhythm, PR, QRS, QT/QTc, axis, per-lead ST; standards-compliant "
        "rendering; retrieval-grounded explanation",
        "Faculty validation pending. P-wave coverage 74%. Educational pre/post study "
        "not yet conducted.",
    ),
]

COL_FRACTIONS = (0.045, 0.215, 0.275, 0.215, 0.250)
COL_TITLES = ("Sr\nNo.", "Paper (Authors)", "Key Findings", "Aspects Addressed", "Limitations")


def render_slide_png(out: Path, dpi: int = 220) -> Path:
    """One-slide PNG of the same table, sized for 16:9."""
    import textwrap

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.family": ["Arial", "DejaVu Sans"]})
    fig_w, fig_h = 16.0, 9.0
    fig = plt.figure(figsize=(fig_w, fig_h))
    # Axes span the whole figure so table coordinates and title coordinates
    # are the same space. With matplotlib's default inset axes the table
    # lands well to the right of a fig.text() title.
    ax = fig.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    left, right = 0.028, 0.972
    width = right - left
    edges = [left]
    for frac in COL_FRACTIONS:
        edges.append(edges[-1] + frac * width)

    body_fs, title_fs = 11.6, 12.0
    # ~95 characters per inch at this size; used only to choose wrap widths.
    chars = [max(8, int((edges[i + 1] - edges[i]) * fig_w * 10.4)) for i in range(5)]

    def wrap(text: str, col: int) -> list[str]:
        return textwrap.wrap(text, chars[col]) or [""]

    rows_lines = []
    for title, authors, *rest in SHORT_ROWS:
        cells = [[""], wrap(title, 1) + wrap(authors, 1)]
        cells += [wrap(t, i + 2) for i, t in enumerate(rest)]
        rows_lines.append(cells)

    line_h = 0.0315
    pad = 0.013
    heights = [max(len(c) for c in cells) * line_h + 2 * pad for cells in rows_lines]
    header_h = 0.062

    top = 0.855
    total = header_h + sum(heights)
    if top - total < 0.03:  # scale to fit if the content grew
        scale = (top - 0.03) / total
        heights = [h * scale for h in heights]
        line_h *= scale
        header_h *= scale

    # Header
    y = top - header_h
    for i, name in enumerate(COL_TITLES):
        ax.add_patch(mpatches.Rectangle((edges[i], y), edges[i + 1] - edges[i], header_h,
                                        facecolor="#4472C4", edgecolor="white", linewidth=1.2))
        ax.text(edges[i] + 0.006, y + header_h / 2, name.replace("\n", " "),
                va="center", ha="left", fontsize=12.6, fontweight="bold", color="white")

    for r, (cells, h) in enumerate(zip(rows_lines, heights, strict=True)):
        y -= h
        is_ours = SHORT_ROWS[r][0].startswith("PROPOSED")
        fill = "#D9EAD3" if is_ours else ("#DCE3F4" if r % 2 == 0 else "#C7D2EA")
        for i in range(5):
            ax.add_patch(mpatches.Rectangle((edges[i], y), edges[i + 1] - edges[i], h,
                                            facecolor=fill, edgecolor="white", linewidth=1.2))

        ax.text((edges[0] + edges[1]) / 2, y + h / 2, str(r + 1), ha="center", va="center",
                fontsize=12.4, fontweight="bold", color="#1A1A1A")

        for i in range(1, 5):
            lines = cells[i]
            ty = y + h - pad - line_h * 0.62
            for j, line in enumerate(lines):
                bold = i == 1 and j < len(wrap(SHORT_ROWS[r][0], 1))
                ax.text(edges[i] + 0.006, ty, line, ha="left", va="center",
                        fontsize=title_fs if bold else body_fs,
                        fontweight="bold" if bold else "normal", color="#1A1A1A")
                ty -= line_h

    ax.text(left, 0.945, "Literature Survey", fontsize=25, fontweight="bold",
            color="#1A1A1A", ha="left", va="top")

    out.parent.mkdir(parents=True, exist_ok=True)
    # No bbox_inches="tight": the output must stay exactly 16:9 for a slide.
    fig.savefig(out, dpi=dpi, facecolor="white")
    plt.close(fig)
    return out
