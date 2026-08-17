#!/usr/bin/env python3
"""
job-hunting install self-check.

Two gaps this closes, both of the same shape: something the package
depends on absolutely, that the install can silently skip.

GAP 1 — the submit hook (Rule 1's third enforcement layer).
security/hooks/verify-submit-approval.py is registered by hand, in a
pre_tool_call block a user pastes into ~/.hermes/config.yaml at install
step 5. Skip that step, mistype the path, or miss the hooks_auto_accept
note, and Rule 1 degrades from an enforced technical boundary to an
instruction in a markdown file that an agent is asked to follow.
NOTHING ANYWHERE VERIFIED THE HOOK WAS LIVE. That is the whole reason
this script exists: the most important safety boundary in the package
was the one with no evidence it was switched on.

GAP 2 — shared/ (pipeline-rules.md Rule 0).
Every skill declares shared/pipeline-rules.md as mandatory reading, and
shared/ sits outside every skill directory, so it is part of no skill's
install unit. `hermes skills install job-hunting-discovery` brings the
skill and none of the rules it says it must follow.

Both failures are silent and both produce a pipeline that reads as
working. A crash would be friendlier.

USAGE
  python3 00-orchestrator/scripts/install-check.py            # human-readable
  python3 00-orchestrator/scripts/install-check.py --json     # machine-readable
  python3 00-orchestrator/scripts/install-check.py --quiet    # exit code only

EXIT CODES
  0  all critical checks passed (warnings may still be present)
  1  at least one CRITICAL check failed
  2  the script could not run at all

This script is READ-ONLY. It repairs nothing, writes nothing, and
changes no config — it reports, and a human fixes. Auto-repairing a
safety hook is exactly the kind of helpfulness that would make the hook
untrustworthy: a gate that reinstalls itself is a gate nobody has to
think about.
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------
# Locations. Overridable by env var so this works on a non-default
# install without editing the file.
# ---------------------------------------------------------------------
HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
CONFIG_PATH = HERMES_HOME / "config.yaml"
SKILL_ROOT = Path(
    os.environ.get("JOB_HUNTING_ROOT", HERMES_HOME / "skills" / "job-hunting")
)

# Rule 0: shared/ files without which the pipeline does not hold.
# Deliberately NOT the full shared/ listing — templates are optional
# until seeded, and flagging them would train people to ignore this
# script's output, which is the failure mode that matters most for a
# check nobody is forced to run.
REQUIRED_SHARED = [
    "shared/pipeline-rules.md",
    "shared/pipeline-rules-addendum.md",
    "shared/applications_db_schema.sql",
]

# Applied in order at install step 4. _3 is superseded by _4 and is
# deliberately absent from a fresh install, so it is not listed.
#
# This list is AUTHORED, deliberately, and must not be derived from
# SKILL_ROOT/shared/. This script checks an INSTALL; deriving what it
# expects from the thing it is checking makes the check circular and it
# would pass the half-copied install it exists to catch. Drift is caught
# instead by dry-run.py, which runs in the repo and asserts this range
# covers every migration on disk.
#
# The previous range(2, 15) stopped four short of README step 4.
SCHEMA_FILES = ["shared/applications_db_schema_addendum.sql"] + [
    f"shared/applications_db_schema_addendum_{i}.sql"
    for i in range(2, 22)
    if i != 3
]

# Tables whose absence means a specific addendum never ran. One
# representative table per addendum that adds any — enough to catch a
# half-applied migration chain without enumerating every table.
SENTINEL_TABLES = {
    "applications": "applications_db_schema.sql",
    "open_gaps": "an addendum (hermes-capability upgrade pass)",
    "career_path_plans": "applications_db_schema_addendum_4.sql",
    "posting_sources": "applications_db_schema_addendum_8.sql",
    "pipeline_pause": "applications_db_schema_addendum_13.sql",
    "career_path_plan_paths": "applications_db_schema_addendum_14.sql",
    "application_build_attempts": "applications_db_schema_addendum_15.sql",
    "fact_supersession_log": "applications_db_schema_addendum_16.sql",
    "fact_influence": "applications_db_schema_addendum_17.sql",
    "portfolio_artifacts": "applications_db_schema_addendum_18.sql",
    "x_follow_engagement_attempts": "applications_db_schema_addendum_19.sql",
    "cron_executions": "applications_db_schema_addendum_20.sql",
}

# _21 adds a column, not a table - check it explicitly the same way.
SENTINEL_COLUMNS = {
    "skill_self_edits": {
        "rotation_week": "applications_db_schema_addendum_21.sql",
    },
}

HOOK_REL = "security/hooks/verify-submit-approval.py"

CRITICAL, WARNING, OK = "CRITICAL", "WARNING", "OK"
results = []


def record(level, check, detail, fix=None):
    results.append({"level": level, "check": check, "detail": detail, "fix": fix})


def _resolve_candidates(token):
    """Every plausible on-disk meaning of a path written in config.yaml.

    Config paths are almost always written as `~/.hermes/skills/...`, but
    HERMES_HOME may point somewhere else — a test install, a container
    mount, a second profile. Resolving only via expanduser() would then
    report a correctly-registered hook as broken, and a check that cries
    wolf is a check people stop running. So: try the literal path, the
    tilde-expanded path, and the same path with a leading `~/.hermes`
    rewritten to the actual HERMES_HOME.
    """
    token = token.rstrip(",;")
    out = [Path(token), Path(os.path.expanduser(token))]
    for prefix in ("~/.hermes/", "$HOME/.hermes/"):
        if token.startswith(prefix):
            out.append(HERMES_HOME / token[len(prefix):])
    return out


# ---------------------------------------------------------------------
# Check 1 — the submit hook. The reason this file exists.
# ---------------------------------------------------------------------
def check_submit_hook():
    hook_path = SKILL_ROOT / HOOK_REL

    if not hook_path.exists():
        record(
            CRITICAL,
            "submit-hook-file",
            f"Rule 1's technical enforcement layer is missing from disk: {hook_path}",
            "Reinstall the package. Do not run the pipeline until this is present.",
        )
        return

    if not os.access(hook_path, os.X_OK):
        record(
            WARNING,
            "submit-hook-exec",
            f"{HOOK_REL} is not executable. Depending on how the hook is "
            "invoked this may or may not matter — it is flagged rather than "
            "assumed either way.",
            f"chmod +x {hook_path}",
        )

    if not CONFIG_PATH.exists():
        record(
            CRITICAL,
            "submit-hook-registered",
            f"No config at {CONFIG_PATH}, so the pre_tool_call hook cannot be "
            "registered. Rule 1 currently rests on procedure alone.",
            "See security/security-setup.md section 3.",
        )
        return

    # Deliberately a substring search rather than a YAML parse. Parsing
    # would need PyYAML, which is one more thing an install can be
    # missing, and this check has to work on the most broken install it
    # will ever see. The cost is that a commented-out registration reads
    # as live — so the reported path is checked against a real one below
    # rather than just found somewhere in the file.
    try:
        config_text = CONFIG_PATH.read_text(errors="replace")
    except Exception as exc:
        record(
            CRITICAL,
            "submit-hook-registered",
            f"Could not read {CONFIG_PATH}: {exc}",
            "Fix file permissions, then re-run this check.",
        )
        return

    registered = "verify-submit-approval.py" in config_text
    if not registered:
        record(
            CRITICAL,
            "submit-hook-registered",
            "verify-submit-approval.py is NOT referenced in config.yaml. "
            "Rule 1 is running on two layers instead of three, and the "
            "missing one is the only layer written for this pipeline "
            "specifically.",
            "Add the pre_tool_call block from security/security-setup.md "
            "section 3, then re-run this check.",
        )
        return

    # Registered under a path that does not exist is worse than not
    # registered: it looks correct in the config and vetoes nothing.
    referenced_ok = False
    for line in config_text.splitlines():
        if "verify-submit-approval.py" not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        for token in stripped.replace('"', " ").replace("'", " ").split():
            if not token.endswith("verify-submit-approval.py"):
                continue
            for candidate in _resolve_candidates(token):
                if candidate.exists():
                    referenced_ok = True

    if not referenced_ok:
        record(
            CRITICAL,
            "submit-hook-path",
            "config.yaml references verify-submit-approval.py, but no path it "
            "gives resolves to a file that exists (or the only references are "
            "commented out). A hook registered at a bad path is silently "
            "inert — it reads as installed and vetoes nothing.",
            f"Correct the path to: {hook_path}",
        )
        return

    record(OK, "submit-hook", "Registered, and the referenced path resolves.")

    # The ownership hook. Same registration mechanism, same silent-skip
    # failure, different boundary — see shared/db-concurrency.md.
    ownership_hook = SKILL_ROOT / "security" / "hooks" / "verify-db-ownership.py"
    if not ownership_hook.exists():
        record(
            CRITICAL,
            "ownership-hook-file",
            f"Missing: {ownership_hook}. Row ownership during a parallel "
            "sweep is instruction-only without it.",
            "Reinstall the package.",
        )
    elif "verify-db-ownership.py" not in config_text:
        record(
            WARNING if not _sweep_enabled() else CRITICAL,
            "ownership-hook-registered",
            "verify-db-ownership.py is not registered in config.yaml. A "
            "delegated subagent that writes to applications.db directly "
            "will succeed, and row ownership becomes a rule the child has "
            "to have been told about and chosen to follow.",
            "Add the second pre_tool_call block from "
            "security/security-setup.md, then re-run this check.",
        )
    else:
        record(OK, "ownership-hook", "Registered.")

    cli_config_text = ""
    try:
        cli_config_text = (HERMES_HOME / "cli-config.yaml").read_text(errors="replace")
    except Exception:
        pass
    if (
        "hooks_auto_accept" not in config_text
        and "hooks_auto_accept" not in cli_config_text
        and not os.environ.get("HERMES_ACCEPT_HOOKS")
    ):
        record(
            WARNING,
            "hooks-auto-accept",
            "Neither hooks_auto_accept (config.yaml or cli-config.yaml) nor "
            "HERMES_ACCEPT_HOOKS is set. The hook is registered, but on "
            "unattended cron runs it may not fire — which is exactly when "
            "nobody is watching.",
            "See security/security-setup.md's hooks_auto_accept note.",
        )


def _sweep_enabled():
    """Is the parallel sweep actually turned on? An unregistered ownership
    hook is CRITICAL if it is and a WARNING if it is not — no subagents
    means no concurrent writers means nothing to enforce yet."""
    try:
        cfg = SKILL_ROOT / "shared" / "pipeline-rules-addendum.md"
        profile = SKILL_ROOT / "shared" / "target-profile.yaml"
        for p in (profile, cfg):
            if p.exists() and "parallel_sweep: true" in p.read_text(errors="replace"):
                return True
    except Exception:
        pass
    return False


def check_sync_hazard():
    """WAL sidecars in a Syncthing/Dropbox folder can tear the database.

    This is the one check here guarding against data LOSS rather than a
    failed write, which is why it looks for the ignore file rather than
    assuming nobody syncs. See db-concurrency.md, "Syncthing and synced
    folders".
    """
    must_ignore = ["applications.db", "applications.db-wal", "applications.db-shm"]
    found_any = False

    for marker, tool in ((".stignore", "Syncthing"), (".dropbox.ignore", "Dropbox")):
        for path in list(SKILL_ROOT.rglob(marker))[:5]:
            found_any = True
            try:
                text = path.read_text(errors="replace")
            except Exception:
                continue
            missing = [p for p in must_ignore if p not in text]
            if missing:
                record(
                    CRITICAL,
                    "sync-hazard",
                    f"{tool} ignore file at {path} does not exclude: "
                    + ", ".join(missing)
                    + ". Syncing a WAL database's sidecar files across machines "
                    "can produce a torn database or a silent .sync-conflict copy "
                    "— data loss, not a failed write.",
                    "Add those patterns to the ignore file. Sync a .backup "
                    "snapshot instead of the live DB.",
                )
            else:
                record(OK, "sync-hazard", f"{tool} ignore file excludes the DB.")

    if not found_any:
        # Absence of an ignore file is not evidence of absence of syncing.
        stray = list((SKILL_ROOT / "shared").glob("*.sync-conflict-*"))
        if stray:
            record(
                CRITICAL,
                "sync-hazard",
                f"Found {len(stray)} sync-conflict file(s) in shared/. Something "
                "is replicating this folder and has already hit a conflict. If any "
                "involve applications.db, writes have been silently lost.",
                "Exclude the DB from sync (db-concurrency.md), then verify the "
                "database against your most recent .backup snapshot.",
            )


# ---------------------------------------------------------------------
# Check 2 — Rule 0. shared/ is in no skill's install unit.
# ---------------------------------------------------------------------
def check_shared():
    if not SKILL_ROOT.exists():
        record(
            CRITICAL,
            "skill-root",
            f"Package root not found at {SKILL_ROOT}.",
            "Set JOB_HUNTING_ROOT, or install the package there.",
        )
        return

    missing = [rel for rel in REQUIRED_SHARED if not (SKILL_ROOT / rel).exists()]
    if missing:
        record(
            CRITICAL,
            "shared-files",
            "Missing from shared/: "
            + ", ".join(missing)
            + ". Every skill declares pipeline-rules.md as mandatory reading, "
            "so this is a package that will read convincingly and follow no "
            "rules. See pipeline-rules.md Rule 0.",
            "Install the whole job-hunting/ folder, not individual skills.",
        )
    else:
        record(OK, "shared-files", "Rule 0 files present.")

    # A skill directory with no SKILL.md is the signature of a partial
    # or interrupted install.
    stages = sorted(
        p for p in SKILL_ROOT.glob("[0-9][0-9]-*") if p.is_dir()
    )
    hollow = [p.name for p in stages if not (p / "SKILL.md").exists()]
    if hollow:
        record(
            CRITICAL,
            "skill-dirs",
            "Stage directories present with no SKILL.md: " + ", ".join(hollow),
            "Reinstall the package whole.",
        )
    elif len(stages) < 21:
        record(
            WARNING,
            "skill-dirs",
            f"Only {len(stages)} numbered stage directories found. A complete "
            "install has 23 (00-23, with 15 merged into 13).",
            None,
        )
    else:
        record(OK, "skill-dirs", f"{len(stages)} stage directories, all with SKILL.md.")


# ---------------------------------------------------------------------
# Check 3 — the schema chain. Install step 4 is a manual sequence of one
# sqlite3 command per migration and there is no reason to assume all ran.
# The count is deliberately not written down here; it was wrong before.
# ---------------------------------------------------------------------
def check_database():
    db_path = SKILL_ROOT / "shared" / "applications.db"
    if not db_path.exists():
        record(
            CRITICAL,
            "database",
            f"No applications.db at {db_path}. Nothing in the pipeline has "
            "anywhere to record state.",
            "Run install step 4's schema sequence.",
        )
        return

    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        present = {
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    except Exception as exc:
        record(CRITICAL, "database", f"Could not open applications.db: {exc}", None)
        return

    absent = {t: src for t, src in SENTINEL_TABLES.items() if t not in present}
    if absent:
        record(
            CRITICAL,
            "schema-chain",
            "Missing tables, so the addendum chain is incomplete: "
            + "; ".join(f"{t} (from {src})" for t, src in absent.items()),
            "Apply the remaining addenda IN ORDER — see README install step 4. "
            "_14 is the one that is NOT idempotent; run it exactly once.",
        )
    else:
        record(OK, "schema-chain", "All sentinel tables present.")

    missing_columns = {}
    for table, cols in SENTINEL_COLUMNS.items():
        if table not in present:
            continue
        try:
            have = {
                r[1]
                for r in con.execute(f"PRAGMA table_info({table})")
            }
        except Exception:
            have = set()
        for col, src in cols.items():
            if col not in have:
                missing_columns[f"{table}.{col}"] = src
    if missing_columns:
        record(
            CRITICAL,
            "schema-chain",
            "Missing columns, so the addendum chain is incomplete: "
            + "; ".join(f"{c} (from {src})" for c, src in missing_columns.items()),
            "Apply the remaining addenda IN ORDER — see README install step 4.",
        )

    # WAL. See shared/db-concurrency.md — the parallel sweep has multiple
    # subagents writing to this file, and SQLite's default on a held lock
    # is to fail the write rather than wait for it.
    try:
        mode = con.execute("PRAGMA journal_mode").fetchone()[0]
    except Exception:
        mode = "unknown"

    if str(mode).lower() != "wal":
        record(
            CRITICAL,
            "db-concurrency",
            f"journal_mode is '{mode}', not WAL. With the parallel pipeline "
            "sweep enabled, a subagent's write that meets a held lock FAILS "
            "rather than waits — leaving an application in a state no stage "
            "picks up again, with nothing raised.",
            "sqlite3 shared/applications.db 'PRAGMA journal_mode=WAL;' — this "
            "is persistent, set once. See shared/db-concurrency.md.",
        )
    else:
        record(OK, "db-concurrency", "journal_mode=WAL.")

    con.close()


# ---------------------------------------------------------------------
# Check 4 — config files that ship as templates and must be copied.
# ---------------------------------------------------------------------
def check_seeded_config():
    required_live = [
        ("shared/target-profile.yaml", CRITICAL),
        ("shared/sources.yaml", CRITICAL),
        ("shared/dynamic-target-calibration.yaml", WARNING),
        ("shared/tier-config.yaml", WARNING),
    ]
    for rel, level in required_live:
        live = SKILL_ROOT / rel
        template = SKILL_ROOT / f"{rel}.template"
        if live.exists():
            continue
        if template.exists():
            record(
                level,
                f"config:{Path(rel).name}",
                f"{rel} does not exist; only the .template does. Nothing reads "
                "a .template file.",
                f"cp {template} {live}, then seed it through the skill's own "
                "elicitation rather than hand-filling it.",
            )
        else:
            record(level, f"config:{Path(rel).name}", f"{rel} missing entirely.", None)


# ---------------------------------------------------------------------
# Check 5 — cron registration. The 23 non-blueprint jobs used to depend
# on hand-typed `hermes cron create` commands, and the 2026-08-15
# diagnosis found most of them never got created. register-jobs.py makes
# it an idempotent process; this check is READ-ONLY (it never creates)
# and merely reports how many manifest jobs are missing from the live
# scheduler.
# ---------------------------------------------------------------------
def check_cron_registration():
    import subprocess as _sp

    reg = SKILL_ROOT / "cron" / "register-jobs.py"
    if not reg.exists():
        record(
            WARNING,
            "cron-registration",
            "cron/register-jobs.py is missing from the package.",
            "Reinstall the package.",
        )
        return
    try:
        proc = _sp.run(
            [sys.executable, str(reg), "--check"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=180,
        )
    except Exception as exc:
        record(
            WARNING,
            "cron-registration",
            f"Could not run register-jobs.py --check: {exc}",
            "Run `python cron/register-jobs.py --check` by hand.",
        )
        return
    missing = [
        line for line in proc.stdout.splitlines()
        if line.startswith("MISSING")
    ]
    if proc.returncode != 0:
        detail = (
            f"{len(missing)} documented cron job(s) are not registered with "
            "the scheduler."
            if missing
            else f"register-jobs.py --check exited {proc.returncode}: "
                 f"{proc.stderr.strip()[:200] or proc.stdout.strip()[:200]}"
        )
        record(
            WARNING,
            "cron-registration",
            detail,
            "Run `python cron/register-jobs.py` once (idempotent), or accept "
            "the four blueprints plus the subset already registered.",
        )
    else:
        record(OK, "cron-registration", "All documented cron jobs registered.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    for check in (
        check_shared,
        check_submit_hook,
        check_database,
        check_seeded_config,
        check_sync_hazard,
        check_cron_registration,
    ):
        try:
            check()
        except Exception as exc:  # a broken check must not hide the others
            record(WARNING, check.__name__, f"Check itself errored: {exc}", None)

    failed = any(r["level"] == CRITICAL for r in results)

    if args.json:
        print(json.dumps({"ok": not failed, "results": results}, indent=2))
    elif not args.quiet:
        for r in results:
            if r["level"] == OK:
                print(f"  ok       {r['check']}: {r['detail']}")
        for r in results:
            if r["level"] == WARNING:
                print(f"\n  WARNING  {r['check']}\n           {r['detail']}")
                if r["fix"]:
                    print(f"           fix: {r['fix']}")
        for r in results:
            if r["level"] == CRITICAL:
                print(f"\n  CRITICAL {r['check']}\n           {r['detail']}")
                if r["fix"]:
                    print(f"           fix: {r['fix']}")
        print()
        print(
            "Install check FAILED — fix the CRITICAL items before running the "
            "pipeline."
            if failed
            else "Install check passed."
        )

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"install-check could not run: {exc}", file=sys.stderr)
        sys.exit(2)
