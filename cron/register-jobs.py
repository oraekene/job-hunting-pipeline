#!/usr/bin/env python3
"""
job-hunting cron registration - idempotent, install-time process.

The four core jobs ship as Hermes blueprints (one-tap /suggestions). The
other 23 jobs documented in cron/cron-jobs.md are NOT blueprints - a skill
can only declare one blueprint, and several jobs share a skill. Historically
those 23 were created by hand-typed `hermes cron create` commands, and the
2026-08-15 diagnosis found 17 of them simply never got created on this
install.

This script makes registration a repeatable process built into the bundle:

  python cron/register-jobs.py            # create every missing job
  python cron/register-jobs.py --check    # read-only: report missing jobs

Idempotency: a job's identity is (schedule, script) for no-agent jobs and
(schedule, skills) for agent jobs. Before creating, the live `hermes cron
list` is consulted; any live job with the same identity is treated as
already registered and skipped, so re-running is a no-op. The manifest below
mirrors cron/cron-jobs.md section by section - that file is the source of
truth; drift between the two is caught by cron job #24's desired-state check.

EXIT CODES
  0  all manifest jobs registered (--check: nothing missing)
  1  at least one job missing or a create failed
  2  the script could not run at all
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
SCRIPTS_DIR = HERMES_HOME / "scripts"
SKILL_ROOT = Path(
    os.environ.get("JOB_HUNTING_ROOT", HERMES_HOME / "skills" / "job-hunting")
)
SECURITY_SCRIPTS = SKILL_ROOT / "security" / "scripts"
BUNDLE_SCRIPTS = SKILL_ROOT / "cron" / "scripts"
REGISTRY = SKILL_ROOT / "cron" / "registered-jobs.json"

ID_RE = re.compile(r"^\s*([0-9a-f]{12})\s+\[")
FIELD_RE = re.compile(r"^\s{4}(\w+):\s*(.*)$")


def parse_live_jobs():
    out = subprocess.run(
        ["hermes", "cron", "list"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=120,
    )
    lines = out.stdout.splitlines()
    jobs = []
    cur = None
    for line in lines:
        m = ID_RE.match(line)
        if m:
            cur = {"id": m.group(1), "skills": set(), "script": None,
                   "schedule": None}
            jobs.append(cur)
            continue
        if cur is None:
            continue
        fm = FIELD_RE.match(line)
        if not fm:
            continue
        key, val = fm.group(1).strip(), fm.group(2).strip()
        if key == "Schedule":
            cur["schedule"] = val
        elif key == "Skills":
            for s in re.split(r"[,\s]+", val):
                if s:
                    cur["skills"].add(s)
        elif key == "Script":
            cur["script"] = val
    return jobs


# --- The manifest. Mirrors cron/cron-jobs.md's `hermes cron create`
# commands section by section. Blueprint jobs (1, 3, 5, 9) are absent by
# design - they are installed via /suggestions, not here.
#
# entry fields:
#   num      - the cron-jobs.md section number (label only)
#   name     - short explicit --name (stable identity for humans)
#   schedule - 5-field cron expression
#   skills   - list of --skill names (agent jobs) OR None
#   script   - filename under ~/.hermes/scripts (no-agent jobs) OR None
#   prompt   - job prompt (agent jobs; optional for no-agent jobs)
#   deliver  - "telegram" where cron-jobs.md passes --deliver, else None
#   no_agent - True for script-only jobs
MANIFEST = [
    dict(num="2", name="Open-web discovery sweep",
         schedule="0 9 * * 1-6", skills=["job-hunting-discovery"],
         prompt=("Check shared/target-profile.yaml's discovery_mode first. If "
                 "it's poll_only, exit immediately with [SILENT] and do nothing "
                 "else. Otherwise, run job-hunting-discovery's open_web_search "
                 "sources only (not the declared-source list, already covered by "
                 "job #1): build platform-dork queries plus a generic query from "
                 "target-profile.yaml, search, visit and extract postings, resolve "
                 "posted_at via the fallback chain in sources.yaml, apply "
                 "exclude_domains if discovery_mode is open_web_excluding, then "
                 "dedupe/filter/queue exactly as job #1 does. Deliver a short "
                 "digest of what this sweep specifically found.")),
    dict(num="4", name="Ghost-check outcome nudge",
         schedule="0 18 * * *", skills=["job-hunting-analytics"],
         prompt=("Run job-hunting-analytics: first run the email-scan outcome "
                 "pass using the himalaya email skill, writing any "
                 "confidently-classified outcomes with outcome_source: "
                 "email_scan. Then find applications with sent_at more than 21 "
                 "days ago and outcome still 'pending'. Ask Kenechukwu for a "
                 "quick status update on each (or mark ghosted if he confirms). "
                 "Use [SILENT] if there's nothing to check.")),
    dict(num="6", name="Question-bank refresh",
         schedule="0 5 1 * *", skills=["job-hunting-context-architect"],
         prompt=("Run an incremental question-bank refresh per "
                 "07-context-architect/references/bank-refresh-automation.md: "
                 "crawl a small batch, curate a candidate bank, diff it against "
                 "the live shared/question_bank.yaml, and deliver the diff as a "
                 "Telegram digest if non-trivial. Do NOT run promote without "
                 "Kenechukwu's explicit approval. Use [SILENT] if the diff is "
                 "empty.")),
    dict(num="7", name="Title-taxonomy refresh",
         schedule="0 6 1 * *", skills=["job-hunting-context-architect"],
         prompt=("Run title_taxonomy_builder.py's enrich command scoped to "
                 "occupations relevant to the current target-profile.yaml "
                 "(--relevant-only), re-embed, and diff the resulting "
                 "market_signals against the live title_taxonomy.sqlite. Deliver "
                 "a digest of what changed. Never overwrite the O*NET-sourced "
                 "base layer, only the market_signals layer. Use [SILENT] if "
                 "nothing changed.")),
    dict(num="8", name="Nightly Tier 1 backup",
         schedule="0 3 * * *", script="backup.sh", no_agent=True,
         deliver="telegram"),
    dict(num="8b", name="Quarterly restore verification",
         schedule="0 4 1 1,4,7,10 *", script="verify-restore.sh",
         no_agent=True, deliver="telegram"),
    dict(num="8c", name="Weekly Tier 2 backup",
         schedule="0 4 * * 0", script="backup-tier2.sh", no_agent=True,
         deliver="telegram"),
    dict(num="10", name="Social listening scan",
         schedule="15 7,10,13,16,19,22 * * 1-6",
         skills=["job-hunting-social-discovery-outreach",
                 "job-hunting-orchestrator"],
         prompt=("Run job-hunting-social-discovery-outreach's discovery half: "
                 "scan configured social_listening sources for hiring-style "
                 "posts, classify each by CTA type (apply_link / "
                 "dm_instructions / email_instructions / unclear). Feed "
                 "apply_link posts into the standard discovery queue exactly as "
                 "job #1 does. For dm_instructions/email_instructions, draft "
                 "outreach records per "
                 "14-social-discovery-outreach/references/cold-dm-email-schema.md "
                 "and stage for approval. Leave unclear posts flagged in the "
                 "digest only. Use [SILENT] if nothing new was found.")),
    dict(num="11", name="Career-pulse journal check-in",
         schedule="0 20 * * 1,3,5", skills=["job-hunting-career-pulse"],
         prompt=("Run job-hunting-career-pulse's journal check-in: send "
                 "Kenechukwu a short, low-key prompt (rotate through: what got "
                 "hard this week, what got resolved, what shipped, who you "
                 "worked with and how it went). Store the raw response in "
                 "career_journal immediately. Flag anything that reads like a "
                 "durable fact and hand it to job-hunting-context-architect as "
                 "a proposed addition - never write directly to "
                 "MEMORY.md/USER.md/target-profile.yaml/the STAR bank. Keep the "
                 "tone practical, not performative.")),
    dict(num="12a", name="Profile monitor weekly",
         schedule="0 9 * * 6", skills=["job-hunting-career-pulse"],
         prompt=("Run job-hunting-career-pulse's profile monitor for GitHub, "
                 "portfolio, and blog only (not LinkedIn - see SKILL.md). Diff "
                 "against the last recorded state, write any changes to "
                 "profile_monitor_events, and surface a digest with a proposed "
                 "context-architect addition for anything that reads like a "
                 "durable fact. Use [SILENT] if nothing changed.")),
    dict(num="12b", name="LinkedIn check monthly",
         schedule="0 9 1 * *", skills=["job-hunting-career-pulse"],
         prompt=("Run job-hunting-career-pulse's LinkedIn check specifically, "
                 "monthly: prefer a Kenechukwu-provided data export or a single "
                 "Kenechukwu-triggered fetch over repeated automated scraping. "
                 "Diff and surface exactly as the weekly job does for other "
                 "channels.")),
    dict(num="13", name="Cold prospecting target-finding",
         schedule="0 8 * * 1", skills=["job-hunting-cold-prospecting"],
         prompt=("Run job-hunting-cold-prospecting's target-finding pass: "
                 "identify up to 5 new candidate targets (companies or "
                 "individuals) matching active shared/pitch-catalog.yaml "
                 "entries' target_customer_profile fields. Delegate research "
                 "for each candidate to a separate subagent in parallel, "
                 "writing to shared/company_research_cache/ or "
                 "shared/individual_research_cache/ per "
                 "17-cold-prospecting/references/target-research.md. Stage "
                 "researched targets with suggested pitch_mode and "
                 "catalog_entry_ids for Kenechukwu to review - do not draft or "
                 "send anything automatically. Use [SILENT] if no qualifying "
                 "candidates were found.")),
    dict(num="14", name="Career path re-evaluation",
         schedule="0 9 * * 1", skills=["job-hunting-career-path-planner"],
         prompt=("Run job-hunting-career-path-planner's re-evaluation pass: "
                 "for every active row in career_path_plans, re-run the gap "
                 "analysis against the current confirmed profile - once per "
                 "open stepping stone and once for the final target. For each "
                 "career_path_plan_roadmap_items row that new evidence closes, "
                 "update its status to resolved, set resolved_by_evidence_ref "
                 "to the specific confirmed fact that closed it, and log the "
                 "transition to career_path_plan_roadmap_item_history with "
                 "trigger=cron_reevaluation. For each career_path_plan_hop_gaps "
                 "row the new evidence satisfies, set evidenced_at and "
                 "evidence_ref. Where a hop is status=achieved, all its "
                 "hop_gaps are evidenced, and estimated_dwell_months has "
                 "elapsed since achieved_at, propose moving it to matured - "
                 "never set matured directly, since maturing a hop triggers a "
                 "re-plan. Log one row to career_path_plan_reevaluations per "
                 "plan for this run, including items_resolved_this_run and a "
                 "short gap_summary_snapshot. Never modify "
                 "target-profile.yaml's title_variants from this job - that "
                 "stays a Kenechukwu-confirmed action via the skill's own Step "
                 "5. Use [SILENT] if nothing changed on any active plan.")),
    dict(num="15", name="Enrichment cycle reset",
         schedule="0 6 * * *", skills=["job-hunting-contact-enrichment"],
         prompt=("Run job-hunting-contact-enrichment's cycle-reset check: for "
                 "every entry in shared/enrichment-tier-usage.yaml, compare "
                 "cycle_resets_at against today. For any entry past its reset "
                 "date, zero used_this_cycle (and tier3_spent_this_cycle_usd "
                 "for the Tier 3 budget entry) and advance cycle_resets_at by "
                 "one month from that date. Never modify monthly_allowance, "
                 "tier3_monthly_budget_usd, or "
                 "shared/enrichment-provider-keys.yaml. Use [SILENT] if "
                 "nothing needed resetting today.")),
    dict(num="16", name="Config drift check",
         schedule="0 9 1 */2 *",
         skills=["job-hunting-interests-profile",
                 "job-hunting-output-templates",
                 "job-hunting-skill-composer",
                 "job-hunting-onboarding"],
         prompt=("Bi-monthly configuration drift check. Both passes read-only "
                 "unless Kenechukwu confirms: (1) job-hunting-interests-profile "
                 "- re-read career-pulse journal entries since the last run "
                 "against memory/interests-profile.md admission criteria; "
                 "propose (never write) any new entry the journal now "
                 "supports. (2) job-hunting-output-templates - compare "
                 "shared/output-templates.yaml against what was actually sent "
                 "since the last run; flag drift where a template no longer "
                 "matches practice. Use [SILENT] if both passes come back "
                 "empty.")),
    dict(num="17", name="Retrieval-index refresh",
         schedule="0 4 * * *", script="refresh-index.sh", no_agent=True,
         prompt="Refresh the retrieval index", deliver="telegram"),
    dict(num="18", name="Pause-expiry check",
         schedule="0 8 * * *", skills=["job-hunting-orchestrator"],
         prompt=("Check shared/applications.db for a pipeline_pause row where "
                 "resume_at has passed and resumed_at IS NULL. If none, "
                 "[SILENT]. If one exists, do not restart any cron jobs - "
                 "message Kenechukwu that the pause has expired and offer to "
                 "run the resume pass in 00-orchestrator/SKILL.md.")),
    dict(num="19", name="LinkedIn connection-flow maintenance",
         schedule="0 8 * * 3", skills=["job-hunting-social-discovery-outreach"],
         prompt=("Run job-hunting-social-discovery-outreach's connection-flow "
                 "maintenance pass: for every social_outreach row with "
                 "connection.status=request_sent_pending_acceptance, check "
                 "connection.sent_at against a 6-month window and set "
                 "status=expired for anything past it. Surface a short digest "
                 "of newly-expired requests only - do not re-draft or re-send "
                 "automatically. This job never checks LinkedIn itself; "
                 "acceptance detection stays kene_confirmed or "
                 "Kenechukwu-triggered computer_use_check per "
                 "14-social-discovery-outreach/references/"
                 "linkedin-connection-flow.md, never a scheduled read of "
                 "LinkedIn's own pages. Use [SILENT] if nothing expired this "
                 "week.")),
    dict(num="20", name="X follow-state check",
         schedule="0 8 * * 3", skills=["job-hunting-social-discovery-outreach"],
         prompt=("Run job-hunting-social-discovery-outreach's X follow-state "
                 "check: for every social_outreach row with "
                 "contact.platform=x and x_follow_state.target_follows_kene != "
                 "true, re-check via the v2 API read. Flip "
                 "follow_back_achieved_at and surface in the digest for any "
                 "target newly following Kenechukwu - these become eligible "
                 "for a direct DM draft. Do not initiate new "
                 "engagement_attempts from this job; engagement is drafted and "
                 "cued through the normal Part B/C flow, this job only reads "
                 "and updates state. Use [SILENT] if nothing changed.")),
    dict(num="21", name="IG/FB window cleanup",
         schedule="0 8 * * 3", skills=["job-hunting-social-discovery-outreach"],
         prompt=("Run job-hunting-social-discovery-outreach's IG/FB window "
                 "cleanup: for every social_outreach row with "
                 "ig_fb_window.opened_at set and expires_at passed with "
                 "messages_sent_in_window=0, set window_closed_unused=true and "
                 "include in the digest. Does not touch opened_at detection - "
                 "that stays event-driven off Kenechukwu's own inbox per "
                 "14-social-discovery-outreach/references/"
                 "ig-fb-engagement-window.md, not this job. Use [SILENT] if "
                 "nothing to flag.")),
    dict(num="22", name="Cron health check",
         schedule="0 9 * * 1", skills=["job-hunting-analytics"],
         prompt=("Run job-hunting-analytics' cron health check: execute "
                 "python3 cron/executions.py report against "
                 "shared/applications.db and surface its output in the weekly "
                 "digest. Do not attempt to repair or re-create any job - "
                 "report only, Kenechukwu decides what to re-register. Use "
                 "[SILENT] if the report says all jobs are within expected "
                 "cadence.")),
    dict(num="23", name="Reconcile-only",
         schedule="0,30 * * * 1-6", script="reconcile-only.py",
         no_agent=True, deliver="telegram",
         prompt=("Run the job-hunting reconciliation-only pass: execute "
                 "python3 reconcile-only.py with no arguments and deliver its "
                 "stdout (the script resolves stranded .outbox items and "
                 "partial-state rows without starting a new pipeline turn). "
                 "No prompt is needed - the script decides.")),
    dict(num="24", name="Verify cron config",
         schedule="0 5 * * *", script="verify-cron-config.py",
         no_agent=True, deliver="telegram",
         sidecars=["cron-desired-state.yaml"],
         prompt=("Verify the job-hunting cron configuration: execute python3 "
                 "verify-cron-config.py with no arguments and deliver its "
                 "stdout (it compares live jobs against "
                 "tools/cron-desired-state.yaml and reports drift). No prompt "
                 "is needed - the script decides.")),
]


def identity_key(entry):
    if entry.get("no_agent"):
        return ("script", entry["schedule"], entry["script"])
    return ("agent", entry["schedule"], frozenset(entry["skills"]))


def live_identities(jobs):
    out = set()
    for j in jobs:
        if not j.get("schedule"):
            continue
        if j.get("script"):
            out.add(("script", j["schedule"], j["script"]))
        elif j.get("skills"):
            out.add(("agent", j["schedule"], frozenset(j["skills"])))
    return out


def ensure_script(entry):
    if not entry.get("script"):
        return None
    name = entry["script"]
    for src_dir in (SECURITY_SCRIPTS, BUNDLE_SCRIPTS):
        src = src_dir / name
        if src.exists():
            SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            dst = SCRIPTS_DIR / name
            if not dst.exists():
                import shutil
                shutil.copy2(src, dst)
                print(f"  copied script -> {dst}")
            for sidecar in entry.get("sidecars", []):
                ssrc = src_dir / sidecar
                sdst = SCRIPTS_DIR / sidecar
                if ssrc.exists() and not sdst.exists():
                    shutil.copy2(ssrc, sdst)
                    print(f"  copied sidecar -> {sdst}")
            return dst
    return None


def build_create_args(entry):
    args = ["hermes", "cron", "create", entry["schedule"]]
    if entry.get("prompt"):
        args.append(entry["prompt"])
    args += ["--name", entry["name"]]
    for skill in entry.get("skills") or []:
        args += ["--skill", skill]
    if entry.get("no_agent"):
        args.append("--no-agent")
    if entry.get("script"):
        args += ["--script", entry["script"]]
    if entry.get("deliver"):
        args += ["--deliver", entry["deliver"]]
    return args


def create_job(entry):
    ensure_script(entry)
    args = build_create_args(entry)
    proc = subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=120,
    )
    if proc.returncode != 0:
        print(f"  CREATE FAILED (exit {proc.returncode}): "
              f"{proc.stderr.strip()[:300]}")
        return False
    created_id = None
    for line in (proc.stdout + "\n" + proc.stderr).splitlines():
        if re.search(r"creat", line, re.I):
            m = re.search(r"([0-9a-f]{12})", line)
            if m:
                created_id = m.group(1)
                break
    registry = []
    if REGISTRY.exists():
        try:
            registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            registry = []
    registry.append({
        "num": entry["num"], "name": entry["name"],
        "schedule": entry["schedule"], "job_id": created_id,
        "created_at_utc": __import__("datetime").datetime.utcnow().isoformat(),
    })
    REGISTRY.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    print(f"  created (id={created_id})")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="read-only: report missing jobs, create nothing")
    args = ap.parse_args()

    try:
        jobs = parse_live_jobs()
    except Exception as exc:
        print(f"could not read `hermes cron list`: {exc}")
        return 2
    live = live_identities(jobs)

    missing = []
    for entry in MANIFEST:
        key = identity_key(entry)
        if key in live:
            continue
        missing.append(entry)

    if args.check:
        if not missing:
            print("all manifest cron jobs are registered")
            return 0
        for e in missing:
            print(f"MISSING  #{e['num']} {e['name']}  schedule={e['schedule']}")
        print(f"{len(missing)} job(s) missing - run "
              "`python cron/register-jobs.py` to register them")
        return 1

    if not missing:
        print("all manifest cron jobs are registered - nothing to do")
        return 0

    print(f"{len(missing)} missing job(s):")
    failed = 0
    for e in missing:
        print(f"  #{e['num']} {e['name']} ({e['schedule']})")
        if not create_job(e):
            failed += 1
    print(f"done - {len(missing) - failed} created, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
