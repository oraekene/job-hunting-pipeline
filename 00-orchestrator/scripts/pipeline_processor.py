#!/usr/bin/env python3
"""
Canonical pipeline processor for cron job #3 (the sweep).

This is the ONLY script the sweep uses to touch application state. It
implements the per-app unit-of-work contract from
00-orchestrator/references/parallel-pipeline-sweep.md and shared/
db-concurrency.md:

  1. claim   — guard an application's discovered -> building transition
               (WHERE status='discovered', rowcount checked) and open its
               build-attempt ledger row. Increments build_attempts at
               dispatch, per addendum 15.
  2. process — verify all 8 stage-output artifacts exist in
               shared/build_artifacts/app_{id}/, then atomically advance
               the row to 'staged' (all-or-nothing). Runs only on rows the
               caller claimed (status='building').
   3. reject  — mark an unavailable posting rejected_by_kene with a reason.
   4. reconcile — run FIRST on every sweep tick: ingest any shared/.outbox/
                files (one transaction per file, rejections recorded with a
                reason), preserve complete builds (reset to 'discovered' as
                'build complete, commit pending'), resolve rows stuck at
                'building' past the staleness threshold with PARTIAL builds
                to 'failed' with outcome 'vanished', and return rows with
                build_attempts < 3 to 'discovered' for retry.
   5. restore — recover a terminal 'failed' row whose 8 artifacts are
                complete (resets to 'discovered', keeps artifacts, records
                a 'restored' attempt marker).
   6. approval-queue — list staged rows with approval_sent_at IS NULL.
   7. mark-approval-pinged — atomically record the Telegram approval ping
                timestamp (NULL-guarded, so two sweeps can't double-ping).

Honors the cron job #3 contract:
  - fully advance to 'staged' OR leave untouched at previous status
  - never calls any submit action
  - records build_attempts ledger rows (outcome staged/failed/vanished/restored)
  - records open_gaps from risk-tactics-gate (stage 9)

Gate columns are read from the stage artifacts, never fabricated: a
title the resume_change_log does not evidence is NOT title_matched, and
an overqualification verdict resume_match.md does not record is NULL.

Usage:
  python pipeline_processor.py --claim 5             # claim app 5 (discovered -> building)
  python pipeline_processor.py --app-id 5            # commit app 5 to 'staged' (all-or-nothing)
  python pipeline_processor.py --reconcile           # ingest outbox + resolve stale/retry rows
  python pipeline_processor.py --limit 3             # process at most 3 discovered apps
  python pipeline_processor.py --reject 6 visa       # reject app 6 for visa
  python pipeline_processor.py --reject 10 gone      # reject app 10 for posting gone
  python pipeline_processor.py --restore 2           # recover terminal failed app with complete build
  python pipeline_processor.py --approval-queue      # staged rows awaiting first Telegram ping
  python pipeline_processor.py --mark-approval-pinged 2  # record the ping atomically

Regression harness (sandboxed, never touches the live DB):
  python 00-orchestrator/scripts/regression-harness.py --skill-dir .
"""
import sqlite3, os, sys, json, datetime, re, shutil, glob

# Windows consoles default to cp1252: printing a naira symbol or em-dash
# mid-transaction raised UnicodeEncodeError and rolled back a commit whose
# open_gaps contained non-ASCII claim text. Reconfigure before anything
# else prints.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.normpath(os.path.join(HERE, "..", ".."))
DB = os.path.join(SKILL_DIR, "shared", "applications.db")
ARTIFACTS_BASE = os.path.join(SKILL_DIR, "shared", "build_artifacts")
OUTBOX = os.path.join(SKILL_DIR, "shared", ".outbox")
OUTBOX_CONSUMED = os.path.join(OUTBOX, "consumed")
OUTBOX_REJECTED = os.path.join(OUTBOX, "rejected")

REQUIRED_ARTIFACTS = [
    "jd_analysis.md",
    "keyword_analysis.json",
    "resume_match.md",
    "resume_change_log.md",
    "cover_letter.txt",
    "application_qa.md",
    "risk_tactics_change_log.md",
    "tailored_resume.docx",
]

PASS_RE = re.compile(r"\[PASS\]")
FAIL_RE = re.compile(r"\[FAIL\]")
BORDERLINE_RE = re.compile(r"\[BORDERLINE PASS\]")
CORRECTED_RE = re.compile(r"\[CORRECTED\]")
UNVERIFIED_RE = re.compile(r"\[UNVERIFIED\]")

# Stale-batch threshold: one sweep cycle (~3.5h) plus margin. A 'building'
# row older than this was built by a run that died or vanished.
STALE_BUILDING_HOURS = 7.0

# Columns the parent is allowed to apply from an outbox file. Everything
# else is ignored — a child's guess at schema is exactly what must not
# land.
OUTBOX_UPDATABLE_COLUMNS = {
    "status", "staged_at", "building_started_at", "build_attempts",
    "build_artifacts_path", "overall_match_score", "keyword_match_score",
    "title_matched", "values_alignment_included", "exact_phrase_count",
    "quantified_bullet_count", "recruiter_named", "structure_mirrored",
    "cover_letter_word_count", "application_channel",
    "risk_gate_pass_count", "risk_gate_fail_count",
    "overqualification_gate", "overqualification_skip_reason",
    "title_delta", "comp_delta_pct",
    "last_failure_stage", "last_failure_reason", "last_failure_at",
    "outcome", "outcome_updated_at", "approval_sent_at", "sent_at",
}

OUTBOX_CHILD_TABLES = {"keyword_analysis", "tactics_log", "open_gaps", "email_insights"}


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def open_db():
    """Connection per shared/db-concurrency.md — WAL, busy timeout, FK on."""
    con = sqlite3.connect(DB, timeout=5.0, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout = 5000")
    con.execute("PRAGMA synchronous = NORMAL")
    con.execute("PRAGMA foreign_keys = ON")
    return con


def get_discovered_apps(con, limit=None):
    """Fetch applications at 'discovered' — the only rows Phase 2 may claim."""
    sql = ("SELECT id, company, role_title, posting_url, source_board, "
           "ats_platform, salary_range, remote_type, status, discovered_at "
           "FROM applications WHERE status = 'discovered' ORDER BY id")
    if limit:
        sql += f" LIMIT {int(limit)}"
    return con.execute(sql).fetchall()


def record_rejection(con, app_id, reason, sub_reason):
    """Mark an application as rejected_by_kene with a reason."""
    now = utcnow()
    c = con.cursor()
    is_visa = "visa" in reason.lower()
    outcome_val = "rejected_visa" if is_visa else "rejected_posting_gone"
    failure_stage = "gate_visa_sponsorship" if is_visa else "stage_2_jd_parser"
    try:
        con.execute("BEGIN IMMEDIATE")
        c.execute(
            "UPDATE applications SET status='rejected_by_kene', "
            "outcome=?, outcome_updated_at=?, last_failure_stage=?, "
            "last_failure_reason=?, last_failure_at=? WHERE id=?",
            (outcome_val, now, failure_stage, sub_reason, now, app_id)
        )
        c.execute(
            "INSERT INTO application_build_attempts "
            "(application_id, attempt_number, started_at, ended_at, outcome, "
            "failure_stage, failure_reason, delegated, artifacts_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (app_id, 1, now, now, 'rejected',
             failure_stage, sub_reason, 0, None)
        )
        con.commit()
        print(f"  REJECTED app {app_id}: {sub_reason}")
        return True
    except Exception as e:
        con.rollback()
        print(f"  ERROR rejecting app {app_id}: {e}", file=sys.stderr)
        return False


def claim_app(con, app_id):
    """Guard the discovered -> building transition and open the attempt row.

    Refuses to claim when the 8 required stage artifacts are absent: a
    claim without artifacts is how a row sat at 'building' for 7 hours,
    got marked 'vanished', and burned a build attempt for nothing
    (app 2 died exactly this way). Artifacts must exist before claim, so
    build_attempts only ever counts real build work.

    Returns True only if this call performed the transition (rowcount==1).
    Zero affected rows means something else already claimed the row — skip
    it, never force it (shared/db-concurrency.md, "Status transitions").
    """
    row = con.execute(
        "SELECT id FROM applications WHERE id=?", (app_id,)
    ).fetchone()
    if row is None:
        print(f"  ERROR: application id={app_id} not found", file=sys.stderr)
        return False
    artifacts_dir, missing = verify_artifacts(app_id)
    if missing:
        print(f"  REFUSED claim app {app_id}: artifacts not ready — "
              f"missing: {missing}")
        return False
    now = utcnow()
    c = con.cursor()
    try:
        con.execute("BEGIN IMMEDIATE")
        c.execute(
            "UPDATE applications SET status='building', building_started_at=?, "
            "build_attempts = COALESCE(build_attempts, 0) + 1 "
            "WHERE id=? AND status='discovered'",
            (now, app_id)
        )
        if c.rowcount == 0:
            con.rollback()
            row = c.execute(
                "SELECT status FROM applications WHERE id=?", (app_id,)
            ).fetchone()
            print(f"  SKIP claim app {app_id}: not 'discovered' "
                  f"(current: {row['status'] if row else 'MISSING'})")
            return False
        row = c.execute(
            "SELECT build_attempts FROM applications WHERE id=?", (app_id,)
        ).fetchone()
        c.execute(
            "INSERT INTO application_build_attempts "
            "(application_id, attempt_number, started_at, ended_at, outcome, "
            "failure_stage, failure_reason, delegated, artifacts_path) "
            "VALUES (?, ?, ?, NULL, NULL, NULL, NULL, 0, ?)",
            (app_id, row["build_attempts"], now,
             f"shared/build_artifacts/app_{app_id}")
        )
        con.commit()
        print(f"  CLAIMED app {app_id} (attempt #{row['build_attempts']})")
        return True
    except Exception as e:
        con.rollback()
        print(f"  ERROR claiming app {app_id}: {e}", file=sys.stderr)
        return False


def verify_artifacts(app_id):
    """Check that all 8 required artifacts exist and are non-empty."""
    artifacts_dir = os.path.join(ARTIFACTS_BASE, f"app_{app_id}")
    missing = []
    for f in REQUIRED_ARTIFACTS:
        p = os.path.join(artifacts_dir, f)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            missing.append(f)
    return artifacts_dir, missing


def count_keyword_score(keyword_json_path):
    """Extract match_score_percentage from keyword_analysis.json.

    Canonical location is the nested `analysis` object (per the
    04-keyword-analysis output contract); the top-level key is accepted
    only as a fallback for older artifacts. Reading only the top level
    landed 0.0 for every stage-4 output that nests the score.
    """
    with open(keyword_json_path, encoding="utf-8") as f:
        kw = json.load(f)
    analysis = kw.get("analysis") or {}
    score = analysis.get("match_score_percentage",
                         kw.get("match_score_percentage", 0))
    return score, kw


def count_resume_match_score(resume_match_path):
    """Extract overall match score from resume_match.md."""
    with open(resume_match_path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"(\d+)%", text)
    if m:
        return int(m.group(1))
    return 0


def count_cover_letter_words(cover_letter_path):
    """Count body words (excluding signature line)."""
    with open(cover_letter_path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    body = "\n".join(
        line for line in lines
        if line.strip() and not line.strip().startswith("Kenechukwu")
    )
    return len(body.split())


def count_risk_gate(gate_log_path):
    """Count PASS/FAIL/BORDERLINE/CORRECTED/UNVERIFIED in risk-gate log."""
    with open(gate_log_path, encoding="utf-8") as f:
        text = f.read()
    n_pass = len(PASS_RE.findall(text))
    n_fail = len(FAIL_RE.findall(text))
    n_borderline = len(BORDERLINE_RE.findall(text))
    n_corrected = len(CORRECTED_RE.findall(text))
    n_unverified = len(UNVERIFIED_RE.findall(text))
    risk_pass = n_pass + n_borderline + n_corrected
    risk_fail = n_fail
    return risk_pass, risk_fail, n_unverified


def extract_gaps_from_risk_log(gate_log_path, app_id, company, role_title):
    """Extract FAIL entries from risk-tactics-change-log as open_gaps rows."""
    with open(gate_log_path, encoding="utf-8") as f:
        text = f.read()
    gaps = []
    # Pattern: [FAIL] <description> — <missing evidence>
    for m in re.finditer(r"\[FAIL\]\s*(.+?)\s*—\s*(.+?)(?=\n|$)", text):
        gaps.append((m.group(1).strip(), m.group(2).strip()))
    return gaps


def read_resume_change_log(rcl_path):
    """Parse resume_change_log.md into its honest gate columns.

    Returns (title_matched, values_alignment_included, quantified_bullet_count).
    A tactic the log does not evidence is NOT reported as applied.
    """
    with open(rcl_path, encoding="utf-8") as f:
        text = f.read()

    title_m = re.search(r"Title matched:\s*(\d+)", text)
    title_matched = int(title_m.group(1)) if title_m else 0

    values_m = re.search(r"Values alignment:\s*(\d+)", text)
    values_alignment_included = 1 if values_m and int(values_m.group(1)) > 0 else 0

    quantified = 0
    tm = re.search(r"^## Tactic 3: Quantified bullets.*?(?=^## Tactic |\Z)", text, re.S | re.M)
    if tm:
        section = tm.group(0)
        quantified = len(re.findall(r"^\s*[-*]\s+", section, re.M))
        quantified += len(re.findall(
            r"^\s*\|.*\[(?:PASS|FAIL|BORDERLINE PASS|CORRECTED|UNVERIFIED)\]\s*\|?\s*$",
            section, re.M))
    return title_matched, values_alignment_included, quantified


def read_overqualification_gate(rm_path):
    """Read Gate 2's verdict from resume_match.md, or NULL when unrecorded.

    DB enum (addendum 6): 'clean' | 'flagged' | 'dropped' | 'skipped'.
    Stage artifacts write human vocabulary — "PASSED (not overqualified)",
    "**clean**", etc. — so the parser accepts the words the artifacts
    actually use (with or without markdown bold) and normalizes to the DB
    enum. A resume_match.md that never states a Gate 2 verdict yields NULL
    (not yet reached) — never a fabricated 'passed'.
    """
    with open(rm_path, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"Gate\s*2[^\n]*?verdict[^\n]*?:\s*([^\n]+)", text, re.I)
    if not m:
        return None, None
    raw = m.group(1).strip().strip("*").strip().lower()
    normalize = {
        "passed": "clean",      # artifacts say "PASSED (not overqualified)"
        "clean": "clean",
        "flagged": "flagged",
        "dropped": "dropped",
        "skipped": "skipped",
    }
    for word, verdict in normalize.items():
        if word in raw:
            skip_m = re.search(r"skip[^\n]*?:\s*([a-z_]+)", text, re.I)
            return verdict, (skip_m.group(1) if skip_m else None)
    # "Not applicable as a blocker — the concern is the opposite
    # (under-scope...)" is a negative overqualification finding: the
    # candidate is NOT overqualified, which is what 'clean' records.
    if "not applicable" in raw and (
            "opposite" in raw or "not overqualified" in raw or "under" in raw):
        return "clean", None
    return None, None


def read_displayed_title(rcl_path):
    """Parse the honest displayed title from the resume change-log.

    The customizer's Tactic 2 section records the title actually shown on
    the resume (e.g. keeps "Product Manager" instead of inflating to
    "Principal"). Returns None when the log records none, so a commit
    leaves the column untouched rather than guessing.
    """
    with open(rcl_path, encoding="utf-8") as f:
        text = f.read()
    # Tactic 2 table form: | Original | Displayed | ... |
    sec = re.search(r"##\s*Tactic\s*2.*?(?=^##\s*Tactic|\Z)", text, re.S | re.M)
    if sec:
        for line in sec.group(0).splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 2 and cells[1] not in ("", "-", "---", "Displayed Title"):
                return cells[1]
    # Legacy form: "Title matched: 1 (Credit Officer -> equivalent role)"
    m = re.search(r"Title matched:\s*(\d+)\s*\(([^)]+)\)", text, re.I)
    if m and int(m.group(1)) == 1:
        return m.group(2).strip()
    return None


def close_open_attempt(c, app_id, outcome, ended_at, stage=None, reason=None,
                       artifacts_path=None):
    """Close the newest still-open (outcome IS NULL) attempt row."""
    row = c.execute(
        "SELECT id FROM application_build_attempts "
        "WHERE application_id=? AND outcome IS NULL "
        "ORDER BY started_at DESC, id DESC LIMIT 1",
        (app_id,)
    ).fetchone()
    if row is None:
        return False
    c.execute(
        "UPDATE application_build_attempts SET ended_at=?, outcome=?, "
        "failure_stage=?, failure_reason=?, artifacts_path=? WHERE id=?",
        (ended_at, outcome, stage, reason, artifacts_path, row["id"])
    )
    return True


def commit_staged_app(con, app_id, build_started):
    """Atomically advance a claimed application row to 'staged'."""
    now = utcnow()
    artifacts_dir, missing = verify_artifacts(app_id)

    if missing:
        print(f"  ARTIFACT CHECK FAILED for app {app_id} — missing/empty: {missing}", file=sys.stderr)
        return False

    print(f"  Artifact check: all 8 stage outputs present for app {app_id}.")

    # Read risk-gate log for counts
    gate_log_path = os.path.join(artifacts_dir, "risk_tactics_change_log.md")
    risk_pass, risk_fail, n_unverified = count_risk_gate(gate_log_path)
    print(f"  Risk-gate: PASS={risk_pass} FAIL={risk_fail} UNVERIFIED={n_unverified}")

    # Read keyword analysis for scores
    kw_path = os.path.join(artifacts_dir, "keyword_analysis.json")
    keyword_score, kw_data = count_keyword_score(kw_path)

    # Read resume match for overall score
    rm_path = os.path.join(artifacts_dir, "resume_match.md")
    match_score = count_resume_match_score(rm_path)

    # Cover letter word count
    cl_path = os.path.join(artifacts_dir, "cover_letter.txt")
    cl_words = count_cover_letter_words(cl_path)

    # Gate columns from the artifacts themselves — never fabricated
    rcl_path = os.path.join(artifacts_dir, "resume_change_log.md")
    title_matched, values_alignment, quantified = read_resume_change_log(rcl_path)
    overqual_gate, overqual_skip = read_overqualification_gate(rm_path)
    displayed_title = read_displayed_title(rcl_path)
    exact_phrases = len(PASS_RE.findall(open(rcl_path, encoding="utf-8").read()))

    # Read application row for company/role + current status
    c = con.cursor()
    row = c.execute(
        "SELECT id, company, role_title, status FROM applications WHERE id=?",
        (app_id,)
    ).fetchone()

    if row is None:
        print(f"  ERROR: application id={app_id} not found", file=sys.stderr)
        return False
    if row["status"] != "building":
        print(f"  NOTICE: app {app_id} at '{row['status']}' — only 'building' "
              f"rows may be committed. Claim it first (--claim).")
        return False

    try:
        con.execute("BEGIN IMMEDIATE")

        # 1) open_gaps from risk-tactics-gate
        gaps = extract_gaps_from_risk_log(
            gate_log_path, app_id, row["company"], row["role_title"]
        )
        for claim, missing_ev in gaps:
            already = c.execute(
                "SELECT id FROM open_gaps WHERE claim_text=? AND application_id=?",
                (claim, app_id)
            ).fetchone()
            if not already:
                c.execute(
                    "INSERT INTO open_gaps (application_id, company, role_title, "
                    "claim_text, missing_evidence, fidelity_mode_at_flag, "
                    "flagged_by, flagged_at) VALUES (?,?,?,?,?,?,?,?)",
                    (app_id, row["company"], row["role_title"], claim,
                     missing_ev, "strict", "09-risk-tactics-gate", utcnow())
                )
                print(f"  open_gaps: inserted '{claim[:60]}...'")

        # 2) close the attempt row opened at claim
        closed = close_open_attempt(c, app_id, "staged", now,
                                    artifacts_path=f"shared/build_artifacts/app_{app_id}")
        if not closed:
            print(f"  WARNING: no open attempt row for app {app_id} — "
                  f"inserting a complete one.")
            attempt = c.execute(
                "SELECT attempt_number FROM application_build_attempts "
                "WHERE application_id=? ORDER BY attempt_number DESC LIMIT 1",
                (app_id,)
            ).fetchone()
            next_attempt = (attempt["attempt_number"] + 1) if attempt else 1
            c.execute(
                "INSERT INTO application_build_attempts "
                "(application_id, attempt_number, started_at, ended_at, outcome, "
                "failure_stage, failure_reason, delegated, artifacts_path) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (app_id, next_attempt, build_started, now, "staged",
                 None, None, 0, f"shared/build_artifacts/app_{app_id}")
            )

        # 3) Advance application row atomically
        c.execute(
            "UPDATE applications SET "
            "status='staged', "
            "staged_at=?, "
            "build_artifacts_path='shared/build_artifacts/app_{id}', "
            "overall_match_score=?, "
            "keyword_match_score=?, "
            "exact_phrase_count=?, "
            "title_matched=?, "
            "title_displayed=COALESCE(?, title_displayed), "
            "values_alignment_included=?, "
            "quantified_bullet_count=?, "
            "recruiter_named=0, "
            "structure_mirrored=0, "
            "cover_letter_word_count=?, "
            "application_channel='full_form', "
            "risk_gate_pass_count=?, "
            "risk_gate_fail_count=?, "
            "overqualification_gate=?, "
            "overqualification_skip_reason=? "
            "WHERE id=?".format(id=app_id),
            (now, match_score, keyword_score, exact_phrases,
             title_matched, displayed_title, values_alignment, quantified,
             cl_words, risk_pass, risk_fail, overqual_gate, overqual_skip,
             app_id)
        )
        con.commit()
        print(f"  COMMIT OK: app {app_id} -> 'staged' (all-or-nothing). "
              f"title_matched={title_matched} overqual_gate={overqual_gate}")
        return True

    except Exception as e:
        con.rollback()
        print(f"  ROLLBACK on error for app {app_id}: {e}", file=sys.stderr)
        return False


def record_failure(con, app_id, stage, reason):
    """Record a failure on a claimed row: keep status, log attempt + reason.

    The row stays at 'building' (or 'discovered' if never claimed) so the
    next tick's reconcile decides retry vs. terminal, per addendum 15.
    """
    now = utcnow()
    c = con.cursor()
    try:
        con.execute("BEGIN IMMEDIATE")
        c.execute(
            "UPDATE applications SET last_failure_stage=?, last_failure_reason=?, "
            "last_failure_at=? WHERE id=?",
            (stage, reason, utcnow(), app_id)
        )
        if not close_open_attempt(c, app_id, "failed", now, stage, reason):
            attempt = c.execute(
                "SELECT attempt_number FROM application_build_attempts "
                "WHERE application_id=? ORDER BY attempt_number DESC LIMIT 1",
                (app_id,)
            ).fetchone()
            next_attempt = (attempt["attempt_number"] + 1) if attempt else 1
            c.execute(
                "INSERT INTO application_build_attempts "
                "(application_id, attempt_number, started_at, ended_at, outcome, "
                "failure_stage, failure_reason, delegated, artifacts_path) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (app_id, next_attempt, now, now, "failed", stage, reason, 0, None)
            )
        con.commit()
        print(f"  FAILURE recorded for app {app_id}: stage={stage}, reason={reason}")
        return True
    except Exception as e:
        con.rollback()
        print(f"  ERROR recording failure for app {app_id}: {e}", file=sys.stderr)
        return False


def reject_outbox_file(fp, reason):
    """Move a malformed outbox file to rejected/ with a visible reason.

    The reason is written to a sidecar next to the rejected file AND
    printed, so rejections stop being silent and permanently invisible.
    """
    dest = os.path.join(OUTBOX_REJECTED, os.path.basename(fp))
    os.replace(fp, dest)
    sidecar = dest + ".reject-reason.txt"
    try:
        with open(sidecar, "w", encoding="utf-8") as f:
            f.write(reason + "\n")
    except Exception:
        pass
    print(f"  Outbox: rejected {os.path.basename(fp)} — {reason}")


def ingest_outbox(con):
    """Ingest shared/.outbox/*.json in application_id order (Phase 1a).

    One transaction per file; consumed -> .outbox/consumed/,
    malformed -> .outbox/rejected/ with a recorded reason and the row set
    to failed. Never half-apply a file (shared/db-concurrency.md, "The
    outbox").
    """
    os.makedirs(OUTBOX_CONSUMED, exist_ok=True)
    os.makedirs(OUTBOX_REJECTED, exist_ok=True)
    if not os.path.isdir(OUTBOX):
        return 0
    files = sorted(
        f for f in glob.glob(os.path.join(OUTBOX, "*.json"))
        if os.path.isfile(f)
    )
    if not files:
        print("  Outbox: empty.")
        return 0

    def app_key(fn):
        base = os.path.basename(fn).split(".")[0]
        try:
            return int(base)
        except ValueError:
            return 0

    files.sort(key=app_key)
    consumed = 0
    rejected = 0
    for fp in files:
        try:
            with open(fp, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            reject_outbox_file(fp, f"unparseable JSON: {e}")
            rejected += 1
            continue
        app_id = payload.get("application_id")
        if not isinstance(app_id, int) or "outcome" not in payload:
            kind = ("missing integer 'application_id'"
                    if not isinstance(app_id, int) else "missing 'outcome'")
            reject_outbox_file(fp, f"malformed outbox record: {kind}")
            rejected += 1
            continue
        c = con.cursor()
        try:
            con.execute("BEGIN IMMEDIATE")
            updates = {
                k: v for k, v in (payload.get("application_updates") or {}).items()
                if k in OUTBOX_UPDATABLE_COLUMNS
            }
            if updates:
                sets = ", ".join(f"{k}=?" for k in updates)
                c.execute(
                    f"UPDATE applications SET {sets} WHERE id=?",
                    (*updates.values(), app_id)
                )
            for table, rows in (payload.get("child_rows") or {}).items():
                if table not in OUTBOX_CHILD_TABLES or not isinstance(rows, list):
                    continue
                for row in rows:
                    if not isinstance(row, dict) or not row:
                        continue
                    row = dict(row)
                    row.setdefault("application_id", app_id)
                    cols = ", ".join(row)
                    marks = ", ".join("?" for _ in row)
                    c.execute(
                        f"INSERT INTO {table} ({cols}) VALUES ({marks})",
                        tuple(row.values())
                    )
            con.commit()
            dest = os.path.join(OUTBOX_CONSUMED, os.path.basename(fp))
            os.replace(fp, dest)
            print(f"  Outbox: ingested app {app_id} ({payload['outcome']}) -> consumed/")
            consumed += 1
        except Exception as e:
            con.rollback()
            reject_outbox_file(fp, f"apply failed for app {app_id}: {e}")
            rejected += 1
    if rejected:
        print(f"  Outbox: {rejected} file(s) rejected — see "
              f"{os.path.relpath(OUTBOX_REJECTED, SKILL_DIR)}/ for reasons.")
    return consumed


def reconcile(con):
    """Phase 1: ingest outbox, resolve stale 'building' rows, retry eligible.

    Order matters (parallel-pipeline-sweep.md Phase 1):
      1. Ingest the outbox FIRST — a file there may explain a 'building'
         row the DB thinks is stale.
      2. Rows at 'building' past STALE_BUILDING_HOURS: set 'failed' with
         outcome 'vanished' (no report at all), move partial artifacts to
         .failed-{n}/.
      3. Rows at 'failed' with build_attempts < 3: return to 'discovered'
         for a later tick. >= 3 stays terminal.
    """
    print("  Reconcile: ingest outbox...")
    ingest_outbox(con)

    c = con.cursor()
    stale = c.execute(
        "SELECT id, building_started_at, build_attempts, build_artifacts_path "
        "FROM applications WHERE status='building' AND building_started_at IS NOT NULL"
    ).fetchall()
    now = datetime.datetime.now(datetime.timezone.utc)
    for row in stale:
        try:
            started = datetime.datetime.fromisoformat(row["building_started_at"].replace("Z", "+00:00"))
        except Exception:
            started = now
        hours = (now - started).total_seconds() / 3600
        if hours < STALE_BUILDING_HOURS:
            continue
        app_id = row["id"]
        # A complete build is finished work, not a dead run. The only thing
        # that can still go wrong is the commit step — and that is exactly
        # what must be retried, not discarded. Only genuinely partial
        # builds get the stale 'vanished' treatment.
        _, missing = verify_artifacts(app_id)
        if not missing:
            try:
                con.execute("BEGIN IMMEDIATE")
                c.execute(
                    "UPDATE applications SET status='discovered', "
                    "building_started_at=NULL, "
                    "last_failure_stage='reconcile', "
                    "last_failure_reason='build complete, commit pending', "
                    "last_failure_at=? WHERE id=?",
                    (utcnow(), app_id)
                )
                close_open_attempt(c, app_id, "failed", utcnow(),
                                   "reconcile", "build complete, commit pending")
                con.commit()
                print(f"  Reconcile: app {app_id} complete build preserved — "
                      f"reset to 'discovered' (commit pending).")
            except Exception as e:
                con.rollback()
                print(f"  ERROR reconciling app {app_id}: {e}", file=sys.stderr)
            continue
        # Move any partial output aside — evidence, not a resume point.
        src = os.path.join(ARTIFACTS_BASE, f"app_{app_id}")
        if os.path.isdir(src):
            dest = f"{src}.failed-{row['build_attempts']}"
            if not os.path.exists(dest):
                os.replace(src, dest)
                print(f"  Reconcile: app {app_id} partial artifacts -> {os.path.basename(dest)}/")
        try:
            con.execute("BEGIN IMMEDIATE")
            c.execute(
                "UPDATE applications SET status='failed', "
                "last_failure_stage='reconcile', "
                "last_failure_reason='vanished — no report after %.1fh', "
                "last_failure_at=? WHERE id=?" % STALE_BUILDING_HOURS,
                (utcnow(), app_id)
            )
            close_open_attempt(c, app_id, "vanished", utcnow(),
                               "reconcile", "no report after %.1fh" % STALE_BUILDING_HOURS)
            con.commit()
            print(f"  Reconcile: app {app_id} stale 'building' -> 'failed' (vanished)")
        except Exception as e:
            con.rollback()
            print(f"  ERROR reconciling app {app_id}: {e}", file=sys.stderr)

    # Retry pass — rows that failed but never burned their 3 attempts.
    retryable = c.execute(
        "SELECT id, build_attempts FROM applications "
        "WHERE status='failed' AND build_attempts < 3"
    ).fetchall()
    for row in retryable:
        c.execute(
            "UPDATE applications SET status='discovered', building_started_at=NULL "
            "WHERE id=? AND status='failed'",
            (row["id"],)
        )
        if c.rowcount:
            print(f"  Reconcile: app {row['id']} -> 'discovered' (retry, "
                  f"attempt {row['build_attempts']}/3)")
    return len(retryable)


def restore_app(con, app_id, dry_run=False):
    """Recover a terminal 'failed' row whose 8 artifacts are complete.

    Only resets state; gate values are re-parsed from the artifacts at the
    next commit, same code path as a normal commit — restore never writes
    gate values directly. The attempt ledger gets a distinct 'restored'
    marker so analytics can tell a restored build from a fresh one.
    """
    artifacts_dir, missing = verify_artifacts(app_id)
    if missing:
        print(f"  RESTORE REFUSED for app {app_id}: build incomplete — "
              f"missing/empty: {missing}", file=sys.stderr)
        print(f"  Suggest: delete the row via discovery cleanup, or rebuild "
              f"the artifacts, then restore.")
        return False
    row = con.execute(
        "SELECT id, status FROM applications WHERE id=?", (app_id,)
    ).fetchone()
    if row is None:
        print(f"  ERROR: application id={app_id} not found", file=sys.stderr)
        return False
    if row["status"] != "failed":
        print(f"  RESTORE REFUSED for app {app_id}: row is '{row['status']}' — "
              f"restore only recovers terminal 'failed' rows. Staged rows "
              f"must go through approval, not be silently un-staged.",
              file=sys.stderr)
        return False
    if dry_run:
        print(f"  [DRY RUN] Would restore app {app_id} "
              f"(current: {row['status']}) -> 'discovered', artifacts kept at "
              f"{artifacts_dir}, attempt ledger gets 'restored' marker.")
        return True
    try:
        con.execute("BEGIN IMMEDIATE")
        con.execute(
            "UPDATE applications SET status='discovered', "
            "building_started_at=NULL, staged_at=NULL, "
            "build_artifacts_path=? WHERE id=?",
            (f"shared/build_artifacts/app_{app_id}", app_id)
        )
        attempt = con.execute(
            "SELECT attempt_number FROM application_build_attempts "
            "WHERE application_id=? ORDER BY attempt_number DESC LIMIT 1",
            (app_id,)
        ).fetchone()
        next_attempt = (attempt["attempt_number"] + 1) if attempt else 1
        con.execute(
            "INSERT INTO application_build_attempts "
            "(application_id, attempt_number, started_at, ended_at, outcome, "
            "failure_stage, failure_reason, delegated, artifacts_path) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (app_id, next_attempt, utcnow(), utcnow(), "restored",
             "restore", "terminal failed row recovered; complete build kept",
             0, f"shared/build_artifacts/app_{app_id}")
        )
        con.commit()
        print(f"  RESTORED app {app_id}: -> 'discovered'. Artifacts kept at "
              f"{artifacts_dir}. Prior failure record retained in the ledger.")
        return True
    except Exception as e:
        con.rollback()
        print(f"  ERROR restoring app {app_id}: {e}", file=sys.stderr)
        return False


def approval_queue(con):
    """List staged rows that have never been pinged for approval."""
    rows = con.execute(
        "SELECT id, company, role_title, staged_at FROM applications "
        "WHERE status='staged' AND approval_sent_at IS NULL ORDER BY id"
    ).fetchall()
    if not rows:
        print("  Approval queue: empty — no staged row awaiting a first ping.")
        return []
    print(f"  Approval queue: {len(rows)} staged row(s) awaiting first ping:")
    for r in rows:
        print(f"    app {r['id']} | {r['company']} | {r['role_title']} "
              f"| staged {r['staged_at']}")
    return rows


def mark_approval_pinged(con, app_id):
    """Atomically record the approval ping timestamp.

    The timestamp is written in the same UPDATE as the claim on the row
    (WHERE approval_sent_at IS NULL): two concurrent sweeps cannot both
    ping the same row — exactly one rowcount wins.
    """
    c = con.cursor()
    try:
        con.execute("BEGIN IMMEDIATE")
        c.execute(
            "UPDATE applications SET approval_sent_at=? "
            "WHERE id=? AND status='staged' AND approval_sent_at IS NULL",
            (utcnow(), app_id)
        )
        won = c.rowcount
        con.commit()
        if won:
            print(f"  APPROVAL PING recorded for app {app_id}.")
            return True
        row = c.execute(
            "SELECT status, approval_sent_at FROM applications WHERE id=?",
            (app_id,)
        ).fetchone()
        print(f"  SKIP approval ping for app {app_id}: "
              f"{'missing' if row is None else 'status=' + row['status'] + ', approval_sent_at=' + str(row['approval_sent_at'])}")
        return False
    except Exception as e:
        con.rollback()
        print(f"  ERROR marking approval ping for app {app_id}: {e}", file=sys.stderr)
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Pipeline processor for cron job #3")
    parser.add_argument("--app-id", type=int, help="Commit a single claimed app to 'staged'")
    parser.add_argument("--claim", type=int, help="Claim a single discovered app (-> 'building')")
    parser.add_argument("--reconcile", action="store_true",
                        help="Ingest outbox + resolve stale/retry rows (Phase 1)")
    parser.add_argument("--reject", nargs=2, metavar=("APP_ID", "REASON"),
                        help="--reject APP_ID REASON  (visa | gone)")
    parser.add_argument("--restore", type=int,
                        help="Recover a terminal failed app whose 8 artifacts are complete")
    parser.add_argument("--approval-queue", action="store_true",
                        help="List staged rows with approval_sent_at IS NULL")
    parser.add_argument("--mark-approval-pinged", type=int,
                        help="Atomically record the approval ping timestamp for a staged app")
    parser.add_argument("--limit", type=int,
                        help="Cap the number of discovered apps processed this run")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be done without committing")
    args = parser.parse_args()

    con = open_db()

    # --- Approval queue mode (read-only) ---
    if args.approval_queue:
        approval_queue(con)
        con.close()
        return 0

    # --- Approval ping mode ---
    if args.mark_approval_pinged:
        if args.dry_run:
            print(f"[DRY RUN] Would record approval ping for app {args.mark_approval_pinged}")
            con.close()
            return 0
        ok = mark_approval_pinged(con, args.mark_approval_pinged)
        con.close()
        return 0 if ok else 1

    # --- Restore mode ---
    if args.restore:
        ok = restore_app(con, args.restore, dry_run=args.dry_run)
        con.close()
        return 0 if ok else 1

    # --- Rejection mode ---
    if args.reject:
        app_id = int(args.reject[0])
        reason = args.reject[1]
        sub_reason = (
            "Visa sponsorship not available — job board explicitly states "
            "'Not Available'. User profile requires visa sponsorship."
            if reason == "visa" else
            "Posting returned 404 / content not found — job listing is gone."
        )
        if not args.dry_run:
            ok = record_rejection(con, app_id, reason, sub_reason)
        else:
            ok = True
            print(f"[DRY RUN] Would reject app {app_id} for: {sub_reason}")
        con.close()
        return 0 if ok else 1

    # --- Reconcile mode ---
    if args.reconcile:
        if args.dry_run:
            print("[DRY RUN] Would ingest outbox and resolve stale/retry rows")
            con.close()
            return 0
        reconcile(con)
        con.close()
        return 0

    # --- Claim mode ---
    if args.claim:
        ok = False if args.dry_run else claim_app(con, args.claim)
        if args.dry_run:
            print(f"[DRY RUN] Would claim app {args.claim} (-> 'building')")
        con.close()
        return 0 if ok else 1

    # --- Commit mode (single app) ---
    if args.app_id:
        if args.dry_run:
            artifacts_dir, missing = verify_artifacts(args.app_id)
            if missing:
                print(f"  [DRY RUN] Missing artifacts: {missing}")
            else:
                print(f"  [DRY RUN] All artifacts present in {artifacts_dir}")
            con.close()
            return 0
        row = con.execute(
            "SELECT id FROM applications WHERE id=?", (args.app_id,)
        ).fetchone()
        if row is None:
            print(f"  ERROR: application id={args.app_id} not found", file=sys.stderr)
            con.close()
            return 1
        build_started = utcnow()
        artifacts_dir, missing = verify_artifacts(args.app_id)
        if not missing:
            try:
                mtimes = [os.path.getmtime(os.path.join(artifacts_dir, f))
                          for f in REQUIRED_ARTIFACTS]
                build_started = datetime.datetime.utcfromtimestamp(min(mtimes)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
            except Exception:
                pass
        success = commit_staged_app(con, args.app_id, build_started)
        con.close()
        print("\n=== Pipeline processor complete ===")
        return 0 if success else 1

    # --- Sweep mode: claim + process, bounded by --limit ---
    rows = get_discovered_apps(con, args.limit)
    print(f"Found {len(rows)} application(s) at 'discovered' to process.")

    if args.dry_run:
        for row in rows:
            artifacts_dir, missing = verify_artifacts(row["id"])
            if missing:
                print(f"  [DRY RUN] app {row['id']}: missing artifacts: {missing}")
            else:
                print(f"  [DRY RUN] app {row['id']}: all artifacts present, would commit")
        con.close()
        return 0

    staged_any = False
    failed_any = False
    for row in rows:
        app_id = row["id"]
        print(f"\n--- App {app_id}: {row['company']} | {row['role_title']} ---")
        # claim_app already verifies artifacts; a claim means they exist.
        # The mtime scan below is the only remaining filesystem touch.
        if not claim_app(con, app_id):
            continue

        artifacts_dir = os.path.join(ARTIFACTS_BASE, f"app_{app_id}")
        try:
            mtimes = [os.path.getmtime(os.path.join(artifacts_dir, f))
                      for f in REQUIRED_ARTIFACTS]
            build_started = datetime.datetime.utcfromtimestamp(min(mtimes)).strftime(
                "%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            build_started = utcnow()

        if commit_staged_app(con, app_id, build_started):
            staged_any = True
        else:
            failed_any = True
            print(f"  FAILED to stage app {app_id}")

    con.close()
    print("\n=== Pipeline processor complete ===")
    if failed_any or (rows and not staged_any):
        print(f"  RESULT: staged={staged_any} failures={failed_any} — "
              f"sweep did not fully succeed.", file=sys.stderr)
        return 1
    print(f"  RESULT: staged={staged_any} failures={failed_any} — sweep OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
