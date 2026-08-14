#!/usr/bin/env python3
"""Regression harness for pipeline_processor.py — the staging state machine.

Runs the real processor CLI end-to-end against a THROWAWAY copy of the
applications DB in a temp sandbox, asserting row statuses, gate columns,
exit codes, and artifact preservation. No network, and it never touches
the live shared/applications.db — the DB is copied via the sqlite backup
API and the sandbox is deleted on exit.

Each case prints one GREEN/RED verdict line; the exit code is the number
of red cases. Runtime target: under 30 seconds.

The fixture artifacts are synthetic but shape-exact copies of the real
stage outputs (nested keyword score, Gate 2 vocabulary, Tactic 2 title
table, risk-gate FAIL lines), so each case exercises a real bug pattern:

  claim_commit_stages          happy path claim -> commit -> staged
  sweep_skips_unready          sweep must not claim artifact-less rows   (T02)
  sweep_exits_nonzero_nothing  sweep must exit non-zero when it stages
                               nothing despite discovered rows           (T02)
  reconcile_preserves_complete stale building + complete build: artifacts
                               kept, retryable, distinct reason          (T03)
  reconcile_burns_partial      stale building + partial build: existing
                               move-and-burn behavior stays              (T03)
  keyword_score_nested         analysis.match_score_percentage lands in
                               keyword_match_score (not 0.0)             (T05)
  overqual_vocab_passed        "PASSED (not overqualified)" normalizes to
                               a non-NULL DB gate                        (T05)
  honest_title_persisted       customizer's displayed title lands in
                               title_displayed                           (T05)
  restore_rescues_terminal     --restore recovers a terminal failed row
                               with a complete build                     (T04)
  restore_refuses_incomplete   --restore refuses a partial build         (T04)
  outbox_rejection_reasoned    malformed outbox file is rejected WITH a
                               recorded reason                           (T08)
  outbox_valid_ingests         valid outbox file still ingests           (T08)
  encoding_roundtrip           naira symbol in risk-log FAIL lines lands
                               intact in open_gaps (no mojibake)         (T09)
  approval_queue_lists_staged  staged rows with NULL approval_sent_at
                               appear in the approval queue              (T06)
  approval_ping_atomic         the ping timestamp is written atomically
                               exactly once                              (T06)

Usage:
  python 00-orchestrator/scripts/regression-harness.py --skill-dir .
"""
import argparse
import glob
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

REQUIRED = [
    "jd_analysis.md",
    "keyword_analysis.json",
    "resume_match.md",
    "resume_change_log.md",
    "cover_letter.txt",
    "application_qa.md",
    "risk_tactics_change_log.md",
    "tailored_resume.docx",
]

# ---- fixture artifacts -------------------------------------------------
# Shape-exact mirrors of the real stage outputs, with the values the
# processor mis-parses today baked in (nested keyword score, "PASSED"
# Gate 2 vocabulary, Tactic 2 title table, em-dash FAIL lines, naira).

KEYWORD_JSON = {
    "analysis": {
        "total_keywords_found": 2,
        "total_possible_points": 4,
        "earned_points": 3,
        "raw_match_score_percentage": 75,
        "match_score_percentage": 53,
        "match_rating": "Needs Work",
    },
    "keywords": [
        {"term": "Product Strategy", "category": "Hard Skill", "found_in_resume": True},
        {"term": "GraphQL", "category": "Hard Skill", "found_in_resume": False},
    ],
    "recommendation": "Honest gaps remain.",
}

RESUME_MATCH = """# Resume Match Analysis - FixtureCorp vs Kenechukwu Oraelosi

## Overall Match Score: 53%

## Gate 1 verdict (match score): **HOLD FOR HUMAN APPROVAL**

## Gate 2 verdict (overqualification): **PASSED (not overqualified)**

- `title_delta`: candidate mid-level vs posting Principal - under-scoped, not overqualified.
"""

RESUME_CHANGE_LOG = """# Resume Change-Log - FixtureCorp | Principal Product Manager (app_fixture)
# fidelity_mode: strict

## Tactic 1: Exact-phrase mirroring
| JD Phrase | Evidence Source | Status |
|---|---|---|
| "Product Strategy" | STAR: MVP Delivery | [PASS] |

## Tactic 2: CV title matching
| Original Title | Displayed Title | Evidence | Status |
|---|---|---|---|
| Product Manager (Savecoins) | Product Manager | STAR: MVP Delivery | [PASS] |
| (Deliberate) Do NOT inflate to "Principal Product Manager" | - | mid-level tenure | [PASS - honest, no inflation] |

## Tactic 3: Quantified bullets
- 150 active users - [PASS]
- 40% cycle time - [PASS]

## Tactic 4: Values alignment
- Values alignment: 4 (all evidence-backed)
"""

RISK_LOG = """# RISK TACTICS GATE - CHANGE-LOG (Stage 9)
# Application: app_fixture | FixtureCorp | Principal Product Manager

- [PASS] Exact phrase: "Product Strategy" - evidence: STAR MVP Delivery.
- [PASS] Exact phrase: "Roadmap" - evidence: STAR MVP Delivery.
- [FAIL] Exact phrase: "GraphQL" — evidence: NONE. Blocked.
- [FAIL] Cost claim "NGN 2.3M" — evidence: STAR Savecoins. Blocked.
"""

RISK_LOG_MULTILINE = """# RISK TACTICS GATE - CHANGE-LOG (Stage 9)
# Application: app_fixture | FixtureCorp | Product Manager, Acquisition

### [PASS] User Acquisition / consumer growth launch
- Evidence: STAR "MVP Delivery at Savecoins". VERIFIED.

### [FAIL] Generative Search / SEO growth ownership
- Missing evidence: no professional search or generative-search optimization experience anywhere in memory. NOT applied. - genuine gap, flagged for human; do not paper over.

### [FAIL] Logged-out / sign-up funnel ownership
- Missing evidence: no logged-out experience, trial-to-signup, or funnel conversion work in memory. NOT applied. - genuine gap, flagged for human.

## Final counts
- [PASS]: 1
- [FAIL]: 2
- [BORDERLINE PASS]: 0
"""

RISK_LOG_NAIRA = """# RISK TACTICS GATE - CHANGE-LOG (Stage 9)
# Application: app_fixture | FixtureCorp | Principal Product Manager

- [PASS] Exact phrase: "Product Strategy" - evidence: STAR MVP Delivery.
- [FAIL] Cost claim "₦2.3M first-month volume" — evidence: STAR Savecoins. Blocked.
"""

COVER_LETTER = """Hi FixtureCorp team,

I have owned product strategy end to end, from discovery through launch.

Kenechukwu Oraelosi
"""

APPLICATION_QA = """# Application Q&A - FixtureCorp

## Q1: Why this role?
Answer draft pending Kenechukwu's input.
"""

JD_ANALYSIS = """# JD Analysis - FixtureCorp | Principal Product Manager

## Source
- **Posting URL (canonical)**: https://fixture.example/careers/1

## Role summary
Principal-level product role.
"""


def make_docx(path):
    """A minimal valid docx (zip with the three required parts)."""
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>Kenechukwu Oraelosi - Product Manager</w:t></w:r></w:p></w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)


def write_fixture_artifacts(artifacts_dir, naira=False, multiline_risk=False):
    os.makedirs(artifacts_dir, exist_ok=True)
    risk_log = RISK_LOG_MULTILINE if multiline_risk else (RISK_LOG_NAIRA if naira else RISK_LOG)
    files = {
        "jd_analysis.md": JD_ANALYSIS,
        "keyword_analysis.json": json.dumps(KEYWORD_JSON, ensure_ascii=False),
        "resume_match.md": RESUME_MATCH,
        "resume_change_log.md": RESUME_CHANGE_LOG,
        "cover_letter.txt": COVER_LETTER,
        "application_qa.md": APPLICATION_QA,
        "risk_tactics_change_log.md": risk_log,
    }
    for name, body in files.items():
        with open(os.path.join(artifacts_dir, name), "w", encoding="utf-8") as f:
            f.write(body)
    make_docx(os.path.join(artifacts_dir, "tailored_resume.docx"))


# ---- sandbox ------------------------------------------------------------

class Sandbox:
    def __init__(self, live_db):
        self.root = tempfile.mkdtemp(prefix="jh-regress-")
        scripts_dir = os.path.join(self.root, "00-orchestrator", "scripts")
        shared_dir = os.path.join(self.root, "shared")
        os.makedirs(scripts_dir)
        os.makedirs(shared_dir)
        os.makedirs(os.path.join(shared_dir, "build_artifacts"))
        os.makedirs(os.path.join(shared_dir, ".outbox"))
        shutil.copy2(os.path.join(ROOT, "00-orchestrator", "scripts", "pipeline_processor.py"),
                     os.path.join(scripts_dir, "pipeline_processor.py"))
        self.processor = os.path.join(scripts_dir, "pipeline_processor.py")
        self.db = os.path.join(shared_dir, "applications.db")
        self.artifacts = os.path.join(shared_dir, "build_artifacts")
        self.outbox = os.path.join(shared_dir, ".outbox")
        src = sqlite3.connect(live_db)
        dst = sqlite3.connect(self.db)
        with dst:
            src.backup(dst)
        dst.close()
        src.close()

    def run(self, *args):
        return subprocess.run([sys.executable, self.processor, *args],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", cwd=self.root)

    def q(self, sql, params=()):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()

    def set_row(self, app_id, **cols):
        con = sqlite3.connect(self.db)
        try:
            sets = ", ".join(f"{k}=?" for k in cols)
            con.execute(f"UPDATE applications SET {sets} WHERE id=?", (*cols.values(), app_id))
            con.commit()
        finally:
            con.close()

    def seed_row(self, app_id, status="discovered", attempts=0, started=None,
                 failures_clear=True):
        """Reset a row to a known state for a case."""
        con = sqlite3.connect(self.db)
        try:
            con.execute(
                "UPDATE applications SET status=?, build_attempts=?, "
                "building_started_at=?, staged_at=NULL, build_artifacts_path=NULL, "
                "last_failure_stage=?, last_failure_reason=?, last_failure_at=?, "
                "approval_sent_at=NULL WHERE id=?",
                (status, attempts, started, None, None, None, app_id),
            )
            con.execute("DELETE FROM application_build_attempts WHERE application_id=?", (app_id,))
            con.execute("DELETE FROM open_gaps WHERE application_id=?", (app_id,))
            con.commit()
        finally:
            con.close()

    def open_attempt(self, app_id, attempt_number, started_at):
        con = sqlite3.connect(self.db)
        try:
            con.execute(
                "INSERT INTO application_build_attempts "
                "(application_id, attempt_number, started_at, ended_at, outcome, "
                "failure_stage, failure_reason, delegated, artifacts_path) "
                "VALUES (?,?,?,NULL,NULL,NULL,NULL,0,?)",
                (app_id, attempt_number, started_at,
                 f"shared/build_artifacts/app_{app_id}"),
            )
            con.commit()
        finally:
            con.close()

    def artifacts_of(self, app_id):
        return os.path.join(self.artifacts, f"app_{app_id}")

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


# ---- cases --------------------------------------------------------------

CASES = []


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def staged(sb, app_id):
    return sb.q("SELECT status FROM applications WHERE id=?", (app_id,))[0][0]


@case("claim_commit_stages")
def c_claim_commit(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2))
    r1 = sb.run("--claim", "2")
    r2 = sb.run("--app-id", "2")
    ok = (r1.returncode == 0 and r2.returncode == 0 and staged(sb, 2) == "staged"
          and sb.q("SELECT overall_match_score FROM applications WHERE id=2")[0][0] == 53
          and sb.q("SELECT risk_gate_pass_count FROM applications WHERE id=2")[0][0] == 2
          and sb.q("SELECT risk_gate_fail_count FROM applications WHERE id=2")[0][0] == 2)
    return ok, f"claim={r1.returncode} commit={r2.returncode} status={staged(sb, 2)}"


@case("sweep_skips_unready")
def c_sweep_skips(sb):
    sb.seed_row(5, status="discovered")
    sb.seed_row(11, status="discovered")
    sb.seed_row(12, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(5))
    r = sb.run("--limit", "3")
    s5, s11, s12 = staged(sb, 5), staged(sb, 11), staged(sb, 12)
    a5 = int(sb.q("SELECT build_attempts FROM applications WHERE id=5")[0][0])
    a11 = int(sb.q("SELECT build_attempts FROM applications WHERE id=11")[0][0])
    a12 = int(sb.q("SELECT build_attempts FROM applications WHERE id=12")[0][0])
    ok = (s5 == "staged" and s11 == "discovered" and s12 == "discovered"
          and a5 >= 1 and a11 == 0 and a12 == 0)
    return ok, f"5={s5}(a{a5}) 11={s11}(a{a11}) 12={s12} exit={r.returncode}"


@case("sweep_exits_nonzero_nothing")
def c_sweep_exit(sb):
    sb.seed_row(11, status="discovered")
    sb.seed_row(12, status="discovered")
    r = sb.run("--limit", "3")
    ok = r.returncode != 0
    return ok, f"exit={r.returncode} (want non-zero when nothing staged)"


@case("reconcile_preserves_complete")
def c_reconcile_complete(sb):
    sb.seed_row(5, status="building", attempts=1,
                started="2026-08-01T00:00:00Z")  # 8+ days stale
    sb.open_attempt(5, 1, "2026-08-01T00:00:00Z")
    write_fixture_artifacts(sb.artifacts_of(5))
    r = sb.run("--reconcile")
    arts_kept = os.path.isdir(sb.artifacts_of(5))
    moved = glob.glob(os.path.join(sb.artifacts, "app_5.failed-*"))
    st = staged(sb, 5)
    reason = sb.q("SELECT last_failure_reason FROM applications WHERE id=5")[0][0] or ""
    outcomes = [x[0] for x in sb.q(
        "SELECT outcome FROM application_build_attempts WHERE application_id=5")]
    ok = (arts_kept and not moved and st == "discovered"
          and "complete" in reason.lower() and "vanished" not in outcomes)
    return ok, f"artifacts_kept={arts_kept} moved={len(moved)} status={st} reason='{reason[:40]}' outcomes={outcomes}"


@case("reconcile_burns_partial")
def c_reconcile_partial(sb):
    sb.seed_row(11, status="building", attempts=1,
                started="2026-08-01T00:00:00Z")
    sb.open_attempt(11, 1, "2026-08-01T00:00:00Z")
    ad = sb.artifacts_of(11)
    os.makedirs(ad, exist_ok=True)
    with open(os.path.join(ad, "jd_analysis.md"), "w", encoding="utf-8") as f:
        f.write("partial")
    r = sb.run("--reconcile")
    moved = glob.glob(os.path.join(sb.artifacts, "app_11.failed-*"))
    outcomes = [x[0] for x in sb.q(
        "SELECT outcome FROM application_build_attempts WHERE application_id=11")]
    ok = (bool(moved) and not os.path.isdir(sb.artifacts_of(11))
          and "vanished" in outcomes)
    return ok, f"moved={len(moved)} outcomes={outcomes}"


@case("keyword_score_nested")
def c_keyword_nested(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2))
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    score = sb.q("SELECT keyword_match_score FROM applications WHERE id=2")[0][0]
    ok = score == 53
    return ok, f"keyword_match_score={score} (want 53 from analysis.match_score_percentage)"


@case("overqual_vocab_passed")
def c_overqual(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2))
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    gate = sb.q("SELECT overqualification_gate FROM applications WHERE id=2")[0][0]
    ok = gate in ("clean", "passed") and gate is not None
    return ok, f"overqualification_gate={gate!r} (want normalized from 'PASSED (not overqualified)')"


@case("honest_title_persisted")
def c_title(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2))
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    td = sb.q("SELECT title_displayed FROM applications WHERE id=2")[0][0]
    ok = td == "Product Manager"
    return ok, f"title_displayed={td!r} (want honest 'Product Manager')"


@case("restore_rescues_terminal")
def c_restore(sb):
    sb.seed_row(5, status="failed", attempts=3)
    sb.set_row(5, last_failure_stage="reconcile",
               last_failure_reason="vanished — no report after 7.0h")
    write_fixture_artifacts(sb.artifacts_of(5))
    r1 = sb.run("--restore", "5")
    st1 = staged(sb, 5)
    r2 = sb.run("--claim", "5")
    r3 = sb.run("--app-id", "5")
    st3 = staged(sb, 5)
    markers = [x[0] for x in sb.q(
        "SELECT outcome FROM application_build_attempts WHERE application_id=5")]
    ok = (r1.returncode == 0 and st1 == "discovered"
          and r2.returncode == 0 and r3.returncode == 0 and st3 == "staged"
          and "restored" in markers)
    return ok, f"restore={r1.returncode}->{st1} claim={r2.returncode} commit={r3.returncode}->{st3} markers={markers}"


@case("restore_refuses_incomplete")
def c_restore_incomplete(sb):
    sb.seed_row(11, status="failed", attempts=3)
    ad = sb.artifacts_of(11)
    os.makedirs(ad, exist_ok=True)
    with open(os.path.join(ad, "jd_analysis.md"), "w", encoding="utf-8") as f:
        f.write("partial")
    r = sb.run("--restore", "11")
    st = staged(sb, 11)
    ok = r.returncode != 0 and st == "failed"
    return ok, f"exit={r.returncode} status={st} (want refuse, row untouched)"


@case("open_gaps_multiline_fail")
def c_gaps_multiline(sb):
    # app_11-style risk log: "### [FAIL] Title" + "- Missing evidence: ..."
    # on the next line. The parser must extract these as open_gaps rows
    # and must NOT treat the "- [FAIL]: N" summary line as a gap.
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2), multiline_risk=True)
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    gaps = sb.q("SELECT claim_text FROM open_gaps WHERE application_id=2")
    ok = (len(gaps) == 2
          and "Generative Search" in gaps[0][0]
          and "Logged-out" in gaps[1][0])
    return ok, f"gaps={[g[0][:40] for g in gaps]}"


@case("outbox_rejection_reasoned")
def c_outbox_bad(sb):
    bad = os.path.join(sb.outbox, "99_malformed.json")
    with open(bad, "w", encoding="utf-8") as f:
        json.dump({"company": "NoAppId"}, f)
    r = sb.run("--reconcile")
    rejected = glob.glob(os.path.join(sb.outbox, "rejected", "99_malformed.json"))
    sidecars = glob.glob(os.path.join(sb.outbox, "rejected", "99_malformed*reason*"))
    ok = bool(rejected) and bool(sidecars)
    return ok, f"rejected={len(rejected)} reason_files={len(sidecars)}"


@case("reconcile_silent_when_idle")
def c_reconcile_silent(sb):
    # Nothing to do: no outbox files, no stale building rows, no retryable
    # failed rows. The reconcile-only cron script relies on EMPTY stdout to
    # stay silent in Telegram — a no-op reconcile must print nothing.
    con = sqlite3.connect(sb.db)
    try:
        con.execute("UPDATE applications SET status='discovered', "
                    "building_started_at=NULL")
        con.commit()
    finally:
        con.close()
    r = sb.run("--reconcile")
    ok = r.returncode == 0 and r.stdout.strip() == ""
    return ok, f"exit={r.returncode} stdout={r.stdout!r}"


@case("outbox_valid_ingests")
def c_outbox_good(sb):
    good = os.path.join(sb.outbox, "2_ok.json")
    with open(good, "w", encoding="utf-8") as f:
        json.dump({
            "application_id": 2,
            "outcome": "staged",
            "application_updates": {"cover_letter_word_count": 42},
        }, f)
    r = sb.run("--reconcile")
    consumed = glob.glob(os.path.join(sb.outbox, "consumed", "2_ok.json"))
    wc = sb.q("SELECT cover_letter_word_count FROM applications WHERE id=2")[0][0]
    ok = bool(consumed) and wc == 42
    return ok, f"consumed={len(consumed)} word_count={wc}"


@case("encoding_roundtrip")
def c_encoding(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2), naira=True)
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    claims = [x[0] for x in sb.q(
        "SELECT claim_text FROM open_gaps WHERE application_id=2")]
    ok = any("₦" in c for c in claims) and all("\ufffd" not in c for c in claims)
    return ok, f"gap claims={[c[:40] for c in claims]}"


@case("approval_queue_lists_staged")
def c_queue(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2))
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    r = sb.run("--approval-queue")
    ok = r.returncode == 0 and "2" in r.stdout
    return ok, f"exit={r.returncode} out={r.stdout.strip()[:60]!r}"


@case("approval_ping_atomic")
def c_ping(sb):
    sb.seed_row(2, status="discovered")
    write_fixture_artifacts(sb.artifacts_of(2))
    sb.run("--claim", "2")
    sb.run("--app-id", "2")
    r1 = sb.run("--mark-approval-pinged", "2")
    ts = sb.q("SELECT approval_sent_at FROM applications WHERE id=2")[0][0]
    r2 = sb.run("--mark-approval-pinged", "2")
    ok = r1.returncode == 0 and ts is not None and r2.returncode != 0
    return ok, f"first={r1.returncode} ts_set={ts is not None} second={r2.returncode}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", default=ROOT)
    a = ap.parse_args()
    live_db = os.path.join(a.skill_dir, "shared", "applications.db")
    if not os.path.exists(live_db):
        print(f"live DB not found: {live_db}", file=sys.stderr)
        return 2

    sb = Sandbox(live_db)
    red = 0
    try:
        for name, fn in CASES:
            try:
                ok, detail = fn(sb)
            except Exception as e:
                ok, detail = False, f"{type(e).__name__}: {e}"
            print(f"  {'GREEN' if ok else 'RED'}  {name}" + ("" if ok else f"  -- {detail}"))
            if not ok:
                red += 1
        print(f"\n{len(CASES)-red}/{len(CASES)} cases green")
        return 0 if red == 0 else red
    finally:
        sb.cleanup()


if __name__ == "__main__":
    sys.exit(min(main(), 100))
