#!/usr/bin/env python3
"""01-job-discovery: compatibility wrapper for the canonical discovery runner.

`shared/run_discovery.py` is the canonical runner. This file used to be a
second copy that filtered titles against target-profile.yaml and read Hacker
News through hnrss.org, which returned HTTP 502. It now delegates to the
canonical runner so a later session cannot run the old behavior.
"""
import runpy
from pathlib import Path

CANONICAL = Path(__file__).resolve().parents[2] / "shared" / "run_discovery.py"

if __name__ == "__main__":
    runpy.run_path(str(CANONICAL), run_name="__main__")
