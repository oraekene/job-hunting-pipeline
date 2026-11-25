#!/usr/bin/env python3
"""Add every live job-hunting cron job to the desired-state file.

cron-desired-state.yaml covered 9 jobs while 27 exist, so
verify-cron-config.py reported 17 jobs as UNTRACKED on every run, which is the
warning that teaches you to ignore the checker. This script reads the live
`hermes cron list`, works out which jobs no desired-state entry already claims
by name prefix, and appends an entry for each one.

    python control-plane/track-cron-jobs.py --dry-run
    python control-plane/track-cron-jobs.py --apply

After --apply, `python cron/scripts/verify-cron-config.py` must print nothing
but "no drift" style output; if it prints a mismatch, the generated entry is
wrong and the script is the thing to fix, not the file.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DESIRED = ROOT / "cron" / "scripts" / "cron-desired-state.yaml"
SLUG_RE = re.compile(r"[^a-z0-9]+")


def slug(name, used):
    base = SLUG_RE.sub("-", name.lower()).strip("-")[:40].strip("-")
    candidate, n = base, 2
    while candidate in used:
        candidate = "%s-%d" % (base, n)
        n += 1
    used.add(candidate)
    return candidate


def live_jobs():
    proc = subprocess.run(["hermes", "cron", "list"], capture_output=True,
                          text=True, errors="replace", timeout=180)
    if proc.returncode != 0:
        sys.exit("hermes cron list failed: " + (proc.stderr or proc.stdout)[:400])
    jobs, current = [], None
    for line in proc.stdout.splitlines():
        head = re.match(r"^\s{2}([0-9a-f]{12})\s+\[(\w+)\]", line)
        if head:
            current = {"id": head.group(1), "name": "", "schedule": "", "deliver": "",
                       "script": "", "skills": [], "workdir": "", "no_agent": False,
                       "model": "", "provider": ""}
            jobs.append(current)
            continue
        if current is None:
            continue
        stripped = line.strip()
        if stripped.startswith("Name:") and not current["name"]:
            current["name"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Schedule:"):
            current["schedule"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Deliver:"):
            current["deliver"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Script:"):
            current["script"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Skills:"):
            current["skills"] = [s for s in re.split(r"[,\s]+", stripped.split(":", 1)[1].strip()) if s]
        elif stripped.startswith("Workdir:"):
            current["workdir"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Mode:"):
            current["no_agent"] = "no-agent" in stripped
        elif stripped.startswith("Model:"):
            current["model"] = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Provider:"):
            current["provider"] = stripped.split(":", 1)[1].strip()
    return jobs


def entry_for(job, used):
    entry = {"id": slug(job["name"], used), "match_name": job["name"],
             "schedule": job["schedule"]}
    if job["workdir"]:
        entry["workdir"] = job["workdir"].replace("\\", "/") == str(ROOT).replace("\\", "/") \
            and "{{skill_dir}}" or job["workdir"].replace("\\", "/")
    if job["script"]:
        entry["script"] = job["script"]
    if job["skills"]:
        entry["skills"] = job["skills"]
    entry["no_agent"] = bool(job["no_agent"])
    if job["deliver"]:
        entry["deliver"] = job["deliver"]
    if not job["no_agent"]:
        entry["model"] = job["model"] or "auto"
        entry["provider"] = job["provider"] or "custom"
    return entry


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    text = DESIRED.read_text(encoding="utf-8")
    state = yaml.safe_load(text) or {}
    known = [j.get("match_name", "") for j in state.get("jobs", [])]
    used = {j["id"] for j in state.get("jobs", []) if j.get("id")}

    new = []
    for job in live_jobs():
        if not job["name"]:
            continue
        if any(job["name"].startswith(prefix) or prefix.startswith(job["name"]) for prefix in known if prefix):
            continue
        new.append(entry_for(job, used))

    if not new:
        print("every live job is already covered by the desired state")
        return 0
    print("%d live jobs are untracked; %d entries to add" % (len(new), len(new)))
    for entry in new:
        print("  " + entry["id"] + "  |  " + entry["match_name"][:48] + "  |  " + entry["schedule"])

    if not args.apply:
        return 0

    lines = ["", "# Tracked from the live job list by control-plane/track-cron-jobs.py on",
             "# 2026-11-24. Matching is by exact job name, so a renamed job shows up",
             "# in the drift report instead of silently disappearing from this file."]
    for entry in new:
        lines.append("  - id: " + entry["id"])
        for key in ("match_name", "schedule", "workdir", "script", "skills", "no_agent", "deliver", "model", "provider"):
            if key not in entry:
                continue
            value = entry[key]
            if isinstance(value, list):
                lines.append("    %s: [%s]" % (key, ", ".join(value)))
            elif isinstance(value, bool):
                lines.append("    %s: %s" % (key, "true" if value else "false"))
            elif key == "match_name":
                lines.append("    %s: \"%s\"" % (key, str(value).replace('"', "'")))
            else:
                lines.append("    %s: %s" % (key, value))
    DESIRED.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print("appended %d entries to %s" % (len(new), DESIRED.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())