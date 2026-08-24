#!/usr/bin/env python3
"""Branch tests for security/hooks/verify-submit-approval.py.

Runs the hook as a subprocess with synthetic pre_tool_call payloads and
asserts every branch. Uses a THROWAWAY SQLite DB and marker dir — never
touches shared/applications.db or live session markers.

The hook is copied into the root of a fixture skill tree so its own
script-relative resolution (see resolve_skill_root) finds the fixture's
shared/, not the real install.

Usage:  python security/hooks/test-submit-gate.py
Exit 0 = all branches behave, exit 1 = any failure.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "verify-submit-approval.py"
SESSION = "test-session-0001"

results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  -- {detail}" if detail and not ok else ""))


def build_fixture(tmp):
    """Fixture skill tree with its own DB + active-application marker.

    Placed at <tmp>/skills/job-hunting so the hook's FIRST-PRIORITY
    candidate (HERMES_HOME + skills/job-hunting) resolves here when we
    invoke the hook with HERMES_HOME=<tmp> — without this, the env
    candidates win over script-relative and the test silently hits the
    real install.
    """
    skill_root = tmp / "skills" / "job-hunting"
    marker_dir = skill_root / "shared" / ".active_application"
    marker_dir.mkdir(parents=True)
    db_path = skill_root / "shared" / "applications.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE applications (id INTEGER PRIMARY KEY, approval_decision TEXT)")
    # id 1: canonical 'approve'; id 2: historical 'approved'; id 3: unset; id 4: rejected
    conn.executemany("INSERT INTO applications VALUES (?, ?)",
                     [(1, "approve"), (2, "approved"), (3, None), (4, "reject")])
    conn.commit()
    conn.close()
    # The hook copy sits at the fixture skill root, where its own
    # script-relative candidate search finds <root>/shared/.
    shutil.copy(HOOK, skill_root / "verify-submit-approval.py")
    return skill_root, db_path


def main():
    tmp = Path(tempfile.mkdtemp(prefix="submit-gate-test-"))
    skill_root, _ = build_fixture(tmp)
    hook_under_test = skill_root / "verify-submit-approval.py"

    def run_hook(marker_app_id, payload):
        """(Re)write the active-application marker, then invoke the hook.

        HERMES_HOME points at the fixture tree so the hook's first-priority
        env candidate resolves HERE, not at the real install.
        """
        if marker_app_id is not None:
            (skill_root / "shared" / ".active_application" / f"{SESSION}.json").write_text(
                json.dumps({"application_id": marker_app_id}))
        p = subprocess.run([sys.executable, str(hook_under_test)],
                           input=json.dumps(payload), capture_output=True,
                           text=True, timeout=30,
                           env={**os.environ, "HERMES_HOME": str(tmp)})
        return json.loads(p.stdout.strip() or "{}")

    submit_click = {"code": "js(\"document.querySelector('[data-testid=submit-application]').click()\")"}
    labeled_click = {"ref": "Submit Application button"}

    seq = [
        ("decision='approve' + labeled submit click -> ALLOW",
         1, {"tool_name": "computer_use", "tool_input": labeled_click, "session_id": SESSION}, False),
        ("decision='approved' + browser_exec submit click -> ALLOW",
         2, {"tool_name": "browser_exec", "tool_input": submit_click, "session_id": SESSION}, False),
        ("decision=None + labeled submit click -> BLOCK",
         3, {"tool_name": "computer_use", "tool_input": labeled_click, "session_id": SESSION}, True),
        ("decision='reject' + submit keyword -> BLOCK",
         4, {"tool_name": "browser_exec", "tool_input": {"code": "click 'send application'"},
             "session_id": SESSION}, True),
        ("unwatched tool name -> always ALLOW",
         3, {"tool_name": "web_search", "tool_input": {}, "session_id": SESSION}, False),
        ("watched tool, no submit keyword -> ALLOW",
         3, {"tool_name": "browser_exec", "tool_input": {"code": "# read the page"}, "session_id": SESSION}, False),
        ("no active-application marker for this session -> ALLOW (gate not in authority)",
         None, {"tool_name": "browser_exec", "tool_input": submit_click,
                "session_id": "some-other-session"}, False),
    ]
    for name, marker_id, payload, expect_block in seq:
        out = run_hook(marker_id, payload)
        blocked = out.get("action") == "block"
        check(name, blocked == expect_block, f"got {out}")

    p = subprocess.run([sys.executable, str(hook_under_test)], input="{not json",
                       capture_output=True, text=True, timeout=30)
    out = json.loads(p.stdout.strip() or "{}")
    check("malformed payload fails closed (BLOCK)", out.get("action") == "block")

    failed = [n for n, ok in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", *failed, sep="\n  ")
        sys.exit(1)


if __name__ == "__main__":
    main()
