#!/usr/bin/env python3
"""Reconcile-only cron job — no model turn.

Runs pipeline_processor.py --reconcile (ingest outbox, resolve rows stuck at
'building' past the staleness threshold, return retryable 'failed' rows to
'discovered') and delivers its stdout verbatim. When nothing is stuck the
output is empty, which hermes no-agent jobs treat as silent.

The reconcile pass exists because the full sweep (job #3) dies occasionally —
provider 429s, gateway restarts — and a row left at 'building' would sit
there forever without this safety net.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent / "skills" / "job-hunting"
PROCESSOR = SKILL_DIR / "00-orchestrator" / "scripts" / "pipeline_processor.py"


def main() -> int:
    if not PROCESSOR.is_file():
        sys.stderr.write(f"pipeline_processor.py not found: {PROCESSOR}\n")
        return 1
    result = subprocess.run(
        [sys.executable, str(PROCESSOR), "--reconcile"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
