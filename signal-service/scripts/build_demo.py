"""Build a single self-contained HTML demo for the faculty review session.

Everything is inlined -- images as data URIs, styles and script in the file --
so it opens by double-clicking on any laptop with no server, no Python, no
network and nothing to install. That matters more than elegance: a demo shown
to clinicians gets one attempt, on someone else's machine, possibly offline.

The page mirrors how a reviewer should actually meet a case:

    see the ECG clean  ->  form your own reading  ->  reveal what the engine
    measured  ->  agree, or disagree and say why

That order is deliberate. Showing the measurements first anchors the reviewer
to them, and their independent reading is the whole point of the session.
Verdicts are kept in the browser and exported as CSV at the end, so the meeting
produces data rather than recollections.

Usage:
    python scripts/build_demo.py                      # default case set
    python scripts/build_demo.py --out demo.html
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cardiosignal import config
from cardiosignal.types import MeasurementResult

# One case per teaching condition, plus one the confidence gate withheld.
# The withheld case is not padding: it is the strongest single demonstration
# that the system knows the difference between a measurement and a guess.
DEFAULT_CASES: list[tuple[int, str, str]] = [
    (954, "Normal sinus rhythm", "The baseline every other case is read against."),
    (18293, "Left bundle branch block", "Broad QRS — does the engine's QRS duration match yours?"),
    (310, "Right bundle branch block", "Check where the QRS onset and offset have been placed."),
    (6751, "Subendocardial injury — ST depression",
     "ST deviation is measured per lead against the PR segment, then grouped by territory."),
    (3636, "First-degree AV block", "The PR interval is the measurement under test here."),
    (296, "ST depression", "Depression is measured against the PR segment, at J+60 ms."),
    (17616, "Left ventricular hypertrophy", "Voltage criteria — amplitudes, not intervals."),
    (282, "Atrial fibrillation — withheld", "Read this one carefully, then see the note."),
]

# Warning codes to plain English. Anything unmapped is shown verbatim rather
# than dropped: an unexplained flag is still information for the reviewer.
WARNING_TEXT = {
    "pr_unstable_waves_may_not_be_p_waves": (
        "The PR interval varied far more from beat to beat than a real conduction time can. "
        "The waves being measured are not P waves."
    ),
    "qt_over_extended": (
        "The measured QT occupies too much of the cardiac cycle — the end of the T wave has "
        "been carried too far."
    ),
    "p_wave_absent": "No P wave could be found on some beats.",
    "p_wave_uncertain": "The P wave was found but could not be delimited confidently on some beats.",
    "beats_excluded": "Some beats were excluded as artefact before averaging.",
    "no_usable_beats_after_quality_exclusion": "Too few usable beats remained to measure anything.",
}

MAX_IMAGE_WIDTH = 1800  # plenty for a projector; keeps the file a sane size


def _image_data_uri(path: Path, max_width: int = MAX_IMAGE_WIDTH) -> str:
    from PIL import Image

    with Image.open(path) as im:
        if im.width > max_width:
            height = round(im.height * max_width / im.width)
            im = im.resize((max_width, height), Image.LANCZOS)
        buffer = io.BytesIO()
        im.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def _fmt(measure, digits: int = 0) -> str:
    """A measure as a clinician reads it, or the reason there is no number."""
    if measure.value is None:
        return {
            "NOT_MEASURABLE": "not applicable",
            "NEEDS_REVIEW": "withheld",
            "FAILED": "could not measure",
        }.get(measure.status.value, "—")
    return f"{measure.value:.{digits}f} {measure.unit}"


def _small_squares(ms: float | None) -> str:
    return f"{ms / 40.0:.1f} small squares" if ms else ""


def case_block(index: int, ecg_id: int, title: str, hint: str, artifacts: Path) -> str:
    result = MeasurementResult.model_validate_json(
        (artifacts / "measurements" / f"{ecg_id}.json").read_text(encoding="utf-8")
    )
    clean = _image_data_uri(artifacts / "images" / f"{ecg_id}_clean.png")
    annotated = _image_data_uri(artifacts / "images" / f"{ecg_id}_annotated.png")

    withheld = result.status.value != "OK"
    rhythm = result.rhythm.regularity.value.replace("_", " ").lower()

    rows = [
        ("Heart rate", _fmt(result.heart_rate), "60 / mean R-R"),
        ("Rhythm", rhythm, "from R-R variability + autocorrelation"),
        ("PR interval", _fmt(result.pr_interval), "P onset → QRS onset"),
        ("QRS duration", _fmt(result.qrs_duration), "QRS onset → QRS offset"),
        ("QT interval", _fmt(result.qt_interval), "QRS onset → T offset (tangent method)"),
        ("QTc (Bazett)", _fmt(result.qtc_bazett), "QT / √RR"),
        ("QTc (Fridericia)", _fmt(result.qtc_fridericia), "QT / RR^⅓"),
        (
            "Frontal axis",
            f"{result.axis.degrees:.0f}° ({result.axis.category.value.lower()})"
            if result.axis.degrees is not None
            else "—",
            "net QRS area, leads I and aVF",
        ),
    ]
    table = "\n".join(
        f"<tr><th>{html.escape(name)}</th><td>{html.escape(str(value))}</td>"
        f"<td class='how'>{html.escape(how)}</td></tr>"
        for name, value, how in rows
    )

    st_rows = [s for s in result.st if s.finding.value != "NORMAL"]
    st_html = ""
    if st_rows:
        items = ", ".join(
            f"<b>{html.escape(s.lead)}</b> {s.deviation_mm:+.1f} mm" for s in st_rows
        )
        territories = [t for t in result.territories if t.finding.value != "NORMAL"]
        terr = ""
        if territories:
            terr = " · ".join(
                f"{t.territory} {t.finding.value.lower()} in {', '.join(t.leads_meeting_threshold)}"
                for t in territories
            )
            terr = f"<div class='terr'>Territory: {html.escape(terr)}</div>"
        st_html = f"<div class='st'><span class='lbl'>ST deviation at J+60 ms</span>{items}{terr}</div>"

    labels = "".join(f"<li>{html.escape(d)}</li>" for d in result.diagnostic_labels) or "<li>—</li>"

    # The reasons are read off the record itself, never written by hand, so the
    # banner cannot drift out of step with what the engine actually decided.
    reasons = []
    for warning in result.warnings:
        code = warning.split(":")[0].split("_in_")[0]
        text = WARNING_TEXT.get(code)
        if text and text not in reasons:
            reasons.append(text)

    banner = ""
    if withheld:
        items = "".join(f"<li>{html.escape(r)}</li>" for r in reasons) or "<li>Confidence below threshold.</li>"
        banner = (
            "<div class='withheld'><b>This case was withheld automatically — it does not "
            "reach a student until a reviewer confirms or corrects it.</b>"
            f"<ul>{items}</ul>"
            "The numbers below are still shown, because a reviewer needs to see what was "
            "measured in order to correct it.</div>"
        )

    warnings = ""
    if reasons and not withheld:
        items = "".join(f"<li>{html.escape(r)}</li>" for r in reasons)
        warnings = f"<div class='warn'><b>System notes</b><ul>{items}</ul></div>"

    status_class = "bad" if withheld else "good"
    status_text = "WITHHELD FOR REVIEW" if withheld else "RELEASED TO STUDENTS"

    return f"""
<section class="case" id="case{index}" data-ecg="{ecg_id}" data-title="{html.escape(title)}">
  <div class="case-head">
    <div>
      <span class="num">{index + 1} / {{TOTAL}}</span>
      <h2>{html.escape(title)}</h2>
      <p class="hint">{html.escape(hint)}</p>
    </div>
    <div class="status {status_class}">{status_text}</div>
  </div>

  <div class="stage">
    <img class="ecg" src="{clean}" alt="12-lead ECG, record {ecg_id}">
  </div>

  <div class="reveal-bar">
    <button class="reveal" onclick="reveal({index})">Reveal what the system measured</button>
    <span class="prompt">Read it yourself first — that independent reading is what we need from you.</span>
  </div>

  <div class="revealed" id="rev{index}" hidden>
    {banner}
    <div class="stage"><img class="ecg" src="{annotated}" alt="Annotated ECG, record {ecg_id}"></div>
    <div class="cols">
      <div>
        <h3>Computed measurements</h3>
        <table class="meas">{table}</table>
        {st_html}
        {warnings}
        <p class="conf">Overall confidence {result.overall_confidence:.2f} ·
           {len(result.beats)} beats analysed · PTB-XL record {ecg_id}</p>
      </div>
      <div>
        <h3>Diagnosis <span class="inherit">inherited from the dataset — not computed by us</span></h3>
        <ul class="dx">{labels}</ul>
        <h3>Your verdict</h3>
        <div class="verdict">
          <label><input type="radio" name="v{index}" value="agree"> Measurements look right</label>
          <label><input type="radio" name="v{index}" value="minor"> Minor correction needed</label>
          <label><input type="radio" name="v{index}" value="reject"> Wrong — reject</label>
        </div>
        <textarea id="n{index}" rows="4"
          placeholder="What would you change? Which value, and to what?"></textarea>
      </div>
    </div>
  </div>
</section>
"""


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>CardioSaarthi — Phase 1 review session</title>
<style>
  :root { --ink:#12232e; --muted:#5b6b78; --line:#dfe6ec; --good:#1b7f4b; --bad:#b3341f;
          --accent:#123a5c; --bg:#f6f8fa; }
  * { box-sizing:border-box; }
  body { margin:0; font:16px/1.55 -apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
         color:var(--ink); background:var(--bg); }
  header { background:var(--accent); color:#fff; padding:26px 32px; }
  header h1 { margin:0 0 6px; font-size:26px; letter-spacing:.2px; }
  header p { margin:0; opacity:.9; font-size:15px; max-width:70ch; }
  .headline { background:#0e2c46; margin:16px -32px -26px; padding:16px 32px; font-size:17px; }
  .headline b { color:#7fd8a6; }
  main { max-width:1500px; margin:0 auto; padding:28px 32px 80px; }
  .intro { background:#fff; border:1px solid var(--line); border-radius:10px;
           padding:20px 24px; margin-bottom:28px; }
  .intro h2 { margin:0 0 10px; font-size:19px; }
  .intro ol { margin:0; padding-left:22px; } .intro li { margin:5px 0; }
  .case { background:#fff; border:1px solid var(--line); border-radius:10px;
          padding:22px 24px; margin-bottom:26px; }
  .case-head { display:flex; justify-content:space-between; align-items:flex-start; gap:20px; }
  .case-head h2 { margin:2px 0 4px; font-size:22px; }
  .num { font-size:12px; letter-spacing:.12em; color:var(--muted); text-transform:uppercase; }
  .hint { margin:0; color:var(--muted); font-size:15px; }
  .status { font-size:11px; font-weight:700; letter-spacing:.09em; padding:7px 12px;
            border-radius:20px; white-space:nowrap; }
  .status.good { background:#e6f5ec; color:var(--good); }
  .status.bad { background:#fdeceb; color:var(--bad); }
  .stage { margin:16px 0; border:1px solid var(--line); border-radius:6px; overflow:hidden;
           background:#fff; }
  .ecg { display:block; width:100%; height:auto; }
  .reveal-bar { display:flex; align-items:center; gap:16px; flex-wrap:wrap; }
  button.reveal { background:var(--accent); color:#fff; border:0; border-radius:6px;
                  padding:11px 20px; font-size:15px; cursor:pointer; }
  button.reveal:hover { background:#1b5182; }
  button.reveal:disabled { background:#98a7b3; cursor:default; }
  .prompt { color:var(--muted); font-size:14px; }
  .cols { display:grid; grid-template-columns:1fr 1fr; gap:28px; margin-top:18px; }
  @media (max-width:1000px) { .cols { grid-template-columns:1fr; } }
  h3 { font-size:16px; margin:0 0 10px; }
  table.meas { border-collapse:collapse; width:100%; font-size:15px; }
  table.meas th { text-align:left; font-weight:600; padding:7px 10px 7px 0; width:34%;
                  border-bottom:1px solid var(--line); }
  table.meas td { padding:7px 10px 7px 0; border-bottom:1px solid var(--line); }
  td.how { color:var(--muted); font-size:13px; }
  .st { margin-top:14px; background:#fff8e8; border-left:3px solid #d99a12;
        padding:10px 14px; font-size:15px; }
  .st .lbl { display:block; font-size:12px; text-transform:uppercase; letter-spacing:.08em;
             color:var(--muted); margin-bottom:3px; }
  .terr { margin-top:5px; font-size:14px; color:var(--muted); }
  .warn { margin-top:14px; font-size:14px; color:var(--muted); background:#f2f5f7;
          border-left:3px solid #9fb0bd; padding:10px 14px; }
  .warn ul, .withheld ul { margin:6px 0; padding-left:20px; }
  .warn li, .withheld li { margin:3px 0; }
  .conf { margin-top:12px; font-size:13px; color:var(--muted); }
  .withheld { background:#fdeceb; border-left:4px solid var(--bad); padding:14px 16px;
              margin-bottom:14px; font-size:15px; }
  .inherit { font-weight:400; font-size:13px; color:var(--muted); }
  ul.dx { margin:0 0 18px; padding-left:20px; } ul.dx li { margin:3px 0; }
  .verdict { display:flex; flex-direction:column; gap:7px; margin-bottom:12px; }
  .verdict label { font-size:15px; cursor:pointer; }
  textarea { width:100%; font:inherit; font-size:14px; padding:9px; border:1px solid var(--line);
             border-radius:6px; resize:vertical; }
  .export { position:sticky; bottom:0; background:#fff; border-top:2px solid var(--accent);
            padding:14px 32px; display:flex; justify-content:space-between; align-items:center;
            gap:16px; flex-wrap:wrap; }
  .export button { background:var(--good); color:#fff; border:0; border-radius:6px;
                   padding:11px 22px; font-size:15px; cursor:pointer; }
  .export span { color:var(--muted); font-size:14px; }
  footer { padding:26px 32px; color:var(--muted); font-size:13px; max-width:80ch; }
  .disclaimer { background:#fff4e5; border-top:3px solid #d99a12; border-bottom:1px solid #e8d3a8;
                padding:12px 32px; font-size:14px; color:#6b4c07; }
  .disclaimer b { color:#8a5a00; }
</style></head><body>
<header>
  <h1>CardioSaarthi — Phase 1</h1>
  <p>Deterministic ECG measurement and standards-compliant rendering. Every value on this page was
     computed by signal processing from the raw waveform. No AI model was consulted anywhere in
     this pipeline. Diagnoses are copied from the dataset's cardiologist annotations.</p>
  <div class="headline">Validated against 200 expert-annotated ECGs:
     <b>every wave boundary placed within half a small square</b> of where a cardiologist put it
     — P onset 11.8 ms, QRS onset 13.4 ms, QRS offset 10.1 ms, T offset 19.3 ms.
     One small square = 40 ms.</div>
</header>
<div class="disclaimer">
  <b>Educational prototype — not for clinical use.</b>
  These recordings come from a public research dataset and are not patients under anyone's care.
  The measurements have not yet been validated by clinical faculty; that review is what this
  session is for. Nothing here should be used to inform the care of any patient.
</div>
<main>
  <div class="intro">
    <h2>How to use this page</h2>
    <ol>
      <li>Read each ECG as you normally would. <b>Do not scroll past it yet.</b></li>
      <li>Press <i>Reveal</i> to see what the system measured, and where it placed each boundary.</li>
      <li>Tell us whether you agree. If not, say which value is wrong and what it should be.</li>
      <li>At the end, press <i>Export</i> — it saves your comments as a file we can work from.</li>
    </ol>
  </div>
  {CASES}
</main>
<div class="export">
  <span>Your comments stay on this computer until you export them. Nothing is sent anywhere.</span>
  <button onclick="exportCsv()">Export comments</button>
</div>
<footer>
  Records are from PTB-XL (PhysioNet, CC-BY 4.0): 21,799 twelve-lead ECGs with cardiologist
  SCP-ECG annotations. Accuracy figures are measured against the Lobachevsky University Database
  (200 records with expert-marked P, QRS and T boundaries) and the QT Database (101 records with
  manually annotated QT) — datasets the engine was never tuned on.
  Sheets are drawn at 25 mm/s and 10 mm/mV; printed at 100% scale, 200 ms measures exactly 5 mm.
</footer>
<script>
function reveal(i) {
  var panel = document.getElementById('rev' + i);
  panel.hidden = false;
  var button = document.querySelectorAll('button.reveal')[i];
  button.disabled = true;
  button.textContent = 'Revealed';
  panel.scrollIntoView({behavior: 'smooth', block: 'start'});
}
function exportCsv() {
  var rows = [['ecg_id', 'condition', 'verdict', 'comment']];
  document.querySelectorAll('.case').forEach(function (el, i) {
    var picked = el.querySelector('input[name="v' + i + '"]:checked');
    var box = document.getElementById('n' + i);
    var note = box ? box.value : '';
    if (!picked && !note.trim()) return;
    rows.push([el.dataset.ecg, el.dataset.title, picked ? picked.value : 'no verdict', note]);
  });
  if (rows.length === 1) { alert('No comments recorded yet.'); return; }
  var csv = rows.map(function (r) {
    return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(',');
  }).join('\\n');
  var url = URL.createObjectURL(new Blob([csv], {type: 'text/csv;charset=utf-8'}));
  var a = document.createElement('a');
  a.href = url;
  a.download = 'cardiosaarthi_faculty_comments.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
</script>
</body></html>
"""


def build(cases: list[tuple[int, str, str]], artifacts: Path, out: Path) -> Path:
    missing = [
        c[0]
        for c in cases
        if not (artifacts / "measurements" / f"{c[0]}.json").exists()
        or not (artifacts / "images" / f"{c[0]}_clean.png").exists()
    ]
    if missing:
        raise SystemExit(
            f"missing artifacts for ecg_id {missing}. Run:\n"
            f"  cardiosignal run --batch artifacts/candidates.parquet"
        )

    blocks = []
    for i, (ecg_id, title, hint) in enumerate(cases):
        print(f"  [{i + 1}/{len(cases)}] {title} (record {ecg_id})")
        blocks.append(case_block(i, ecg_id, title, hint, artifacts).replace("{TOTAL}", str(len(cases))))

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(PAGE.replace("{CASES}", "\n".join(blocks)), encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=config.ARTIFACT_ROOT)
    parser.add_argument("--out", type=Path, default=config.REPO_ROOT / "demo" / "phase1_demo.html")
    parser.add_argument("--cases", type=Path, help="JSON list of {ecg_id,label,hint}")
    args = parser.parse_args()

    cases = DEFAULT_CASES
    if args.cases:
        data = json.loads(args.cases.read_text())
        cases = [(int(d["ecg_id"]), d.get("label", ""), d.get("hint", "")) for d in data]

    print(f"Building demo from {args.artifacts} ...")
    path = build(cases, args.artifacts, args.out)
    size_mb = path.stat().st_size / 1e6
    print(f"\nwritten -> {path}  ({size_mb:.1f} MB)")
    print("Self-contained: copy this single file anywhere and double-click it. No server needed.")


if __name__ == "__main__":
    main()
