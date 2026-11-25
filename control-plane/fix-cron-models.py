#!/usr/bin/env python3
"""Repoint job-hunting cron jobs that fail on a provider with no credential.

`hermes cron list` shows every agent job in this bundle dying with
"provider credential missing: No access token found for Nous Portal login",
because the jobs are pinned to a provider whose credential does not exist in
this Hermes home. This script reads the live job list, finds the failing jobs,
and repins them to a provider and model that actually work here.

    python control-plane/fix-cron-models.py --dry-run
    python control-plane/fix-cron-models.py --apply --provider custom --model auto

It is safe by default: without --apply it changes nothing.
"""

import argparse
import re
import subprocess
import sys

ID_RE = re.compile(r"^\s{2}([0-9a-f]{12})\s+\[")


def live_jobs():
    proc = subprocess.run(["hermes", "cron", "list"], capture_output=True,
                          text=True, errors="replace", timeout=180)
    if proc.returncode != 0:
        sys.exit("hermes cron list failed: " + (proc.stderr or proc.stdout)[:400])
    jobs, current = [], None
    for line in proc.stdout.splitlines():
        match = ID_RE.match(line)
        if match:
            current = {"id": match.group(1), "name": "", "state": "", "failing": False}
            jobs.append(current)
            continue
        if current is None:
            continue
        if "Name:" in line and not current["name"]:
            current["name"] = line.split("Name:", 1)[1].strip()
        if "provider credential missing" in line or "401" in line or "401 Unauthorized" in line:
            current["failing"] = True
    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually edit the jobs")
    ap.add_argument("--provider", default="custom")
    ap.add_argument("--model", default="auto")
    ap.add_argument("--only", help="edit only this job id")
    args = ap.parse_args()

    jobs = live_jobs()
    failing = [j for j in jobs if j["failing"] and (not args.only or j["id"] == args.only)]
    print("live jobs: %d, failing on a missing credential: %d" % (len(jobs), len(failing)))
    if not failing:
        print("nothing to repoint")
        return 0

    for job in failing:
        if not args.apply:
            print("  would repin %s  %s" % (job["id"], job["name"][:60]))
            continue
        proc = subprocess.run(["hermes", "cron", "edit", job["id"],
                               "--provider", args.provider, "--model", args.model],
                              capture_output=True, text=True, errors="replace", timeout=180)
        ok = "Updated job" in proc.stdout
        print("  %s %s %s %s" % (job["id"], "OK " if ok else "FAILED", args.provider,
                                 job["name"][:50]))
        if not ok:
            print("      " + (proc.stderr or proc.stdout).strip()[:200])
    return 0 if not failing or args.apply else 0


if __name__ == "__main__":
    sys.exit(main())