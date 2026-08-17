#!/usr/bin/env python3
"""Verify the live hermes cron configuration against the desired state.

The job-hunting pipeline has a history of silent cron drift — wrong script
paths (backup.sh / refresh-index.sh), unpinned workdirs, models pinned to a
dead provider (copilot). This checker makes that drift loud: run it daily as
a no-agent cron job, deliver to telegram, exit 1 only when something drifted.

Desired state lives in cron-desired-state.yaml next to this script. Each
desired job is matched to a live job by name prefix (hermes job ids are
unstable across re-creates, names are not). Checks:

  * job exists and is enabled
  * schedule expression (exact)
  * workdir (exact, with {{hermes_home}} / {{skill_dir}} tokens)
  * script name (exact) and that the file exists under <hermes_home>/scripts/
  * pinned model + provider (exact; None = follow config default)
  * no_agent flag, deliver target, skills list (subset)

Jobs present in the live config but absent from desired state are reported as
UNTRACKED (warn only — they may be one-off user jobs).

Exit codes: 0 all good, 1 drift found, 2 usage/config error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required (pip install pyyaml)\n")
    sys.exit(2)


class DesiredJob:
    def __init__(self, raw: dict):
        self.id = raw.get("id")
        self.match_name = raw.get("match_name")
        self.schedule = raw.get("schedule")
        self.workdir = raw.get("workdir")
        self.script = raw.get("script")
        self.skills = raw.get("skills") or []
        self.model = raw.get("model")
        self.provider = raw.get("provider")
        self.no_agent = bool(raw.get("no_agent", False))
        self.deliver = raw.get("deliver", "local")

    def validate(self) -> Optional[str]:
        if not self.id:
            return "desired job missing id"
        if not self.match_name:
            return f"job {self.id}: match_name required"
        if not self.schedule:
            return f"job {self.id}: schedule required"
        return None


def load_desired(path: Path) -> List[DesiredJob]:
    if not path.is_file():
        raise FileNotFoundError(f"desired-state file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    raw_jobs = (data or {}).get("jobs") or []
    if not raw_jobs:
        raise ValueError(f"no jobs declared in {path}")
    jobs = [DesiredJob(j) for j in raw_jobs]
    for j in jobs:
        err = j.validate()
        if err:
            raise ValueError(f"{path}: {err}")
    return jobs


def load_live(path: Path) -> List[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"jobs.json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    jobs = data if isinstance(data, list) else data.get("jobs", [])
    if isinstance(jobs, dict):
        jobs = list(jobs.values())
    return jobs


def expand(token_value: str, hermes_home: str, skill_dir: str) -> str:
    import os

    return os.path.normpath(
        token_value.replace("{{hermes_home}}", hermes_home).replace("{{skill_dir}}", skill_dir)
    )


def match_live(live: dict, desired: DesiredJob) -> Optional[dict]:
    name = live.get("name") or ""
    if name.startswith(desired.match_name):
        return live
    return None


def schedule_expr(live: dict) -> str:
    sched = live.get("schedule") or {}
    if isinstance(sched, dict):
        return sched.get("expr") or live.get("schedule_display") or ""
    return str(sched)


def check_job(live: dict, desired: DesiredJob, hermes_home: str, skill_dir: str) -> List[str]:
    problems: List[str] = []
    label = f"{desired.id} ({live.get('id', '?')})"
    if not live.get("enabled", False):
        problems.append(f"{label}: disabled")
    if schedule_expr(live) != desired.schedule:
        problems.append(f"{label}: schedule '{schedule_expr(live)}' != '{desired.schedule}'")
    if desired.workdir:
        want = expand(desired.workdir, hermes_home, skill_dir)
        if (live.get("workdir") or "") != want:
            problems.append(f"{label}: workdir '{live.get('workdir')}' != '{want}'")
    if desired.script:
        if (live.get("script") or "") != desired.script:
            problems.append(f"{label}: script '{live.get('script')}' != '{desired.script}'")
        script_path = Path(hermes_home) / "scripts" / desired.script
        if not script_path.is_file():
            problems.append(f"{label}: script file missing: {script_path}")
    if desired.model:
        if (live.get("model") or None) != desired.model:
            problems.append(f"{label}: model '{live.get('model')}' != '{desired.model}'")
    if desired.provider:
        if (live.get("provider") or None) != desired.provider:
            problems.append(f"{label}: provider '{live.get('provider')}' != '{desired.provider}'")
    if bool(live.get("no_agent", False)) != desired.no_agent:
        problems.append(f"{label}: no_agent {live.get('no_agent')} != {desired.no_agent}")
    if (live.get("deliver") or "local") != desired.deliver:
        problems.append(f"{label}: deliver '{live.get('deliver')}' != '{desired.deliver}'")
    live_skills = set(live.get("skills") or [])
    for s in desired.skills:
        if s not in live_skills:
            problems.append(f"{label}: skill '{s}' missing")
    return problems


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hermes-home", default=None, help="hermes home dir (default: env HERMES_HOME, else %LOCALAPPDATA%/hermes on Windows, else ~/.hermes)")
    parser.add_argument("--desired", type=Path, default=Path(__file__).parent / "cron-desired-state.yaml")
    args = parser.parse_args(argv)

    hermes_home = args.hermes_home or os_environ("HERMES_HOME") or default_hermes_home()
    if not Path(hermes_home).is_dir():
        sys.stderr.write(f"hermes home not found: {hermes_home}\n")
        return 2
    skill_dir = str(Path(hermes_home) / "skills" / "job-hunting")

    try:
        desired = load_desired(args.desired)
        live_jobs = load_live(Path(hermes_home) / "cron" / "jobs.json")
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2

    problems: List[str] = []
    seen_ids = set()
    for djob in desired:
        match = next((j for j in live_jobs if match_live(j, djob)), None)
        if match is None:
            problems.append(f"{djob.id}: job not found (expected name prefix '{djob.match_name}')")
            continue
        seen_ids.add(match.get("id"))
        problems.extend(check_job(match, djob, hermes_home, skill_dir))

    tracked_ids = {j.get("id") for j in live_jobs if j.get("enabled", False)}
    for j in live_jobs:
        jid = j.get("id")
        if jid not in seen_ids and jid in tracked_ids:
            problems.append(f"untracked job {jid} ('{j.get('name')}') — absent from desired state")

    if problems:
        print("CRON CONFIG DRIFT DETECTED:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[SILENT] cron config matches desired state ({} jobs)".format(len(desired)))
    return 0


def os_environ(key: str) -> Optional[str]:
    import os

    return os.environ.get(key)


def default_hermes_home() -> str:
    import os
    import sys

    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            candidate = str(Path(local) / "hermes")
            if Path(candidate).is_dir():
                return candidate
    return str(Path.home() / ".hermes")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
