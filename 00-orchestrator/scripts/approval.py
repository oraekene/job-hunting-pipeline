#!/usr/bin/env python3
"""Portable approval CLI — the human half of Rule 1.

The pipeline's authority to submit comes from exactly one place: an
explicit human approval recorded in shared/applications.db. This script is
how that record gets written, independent of which channel carried the
request. Today the channel is Telegram; in a plugin install it can be a
CLI prompt, a webhook, a chat bridge, or a file. The record is the
contract, not the channel.

    python 00-orchestrator/scripts/approval.py --request 233
        Print the approval request for one application: who, what, score,
        gate verdicts, honest gaps and the artifacts a human should read.
        Any channel can carry this text.

    python 00-orchestrator/scripts/approval.py --record 233 --decision approve \
        --by "Kenechukwu" [--note "overrides gate: on-site London accepted"]
        Write the decision. `approve` and `skip` are the only two values.
        `--by` is mandatory: an approval with no named human is not one.

    python 00-orchestrator/scripts/approval.py --list
        List applications that are staged and have no decision yet.

    python 00-orchestrator/scripts/approval.py --check 233
        Read the decision without writing it (the submit-guate's twin).

The write is atomic and NULL-guarded: recording a decision twice is an
error, not an overwrite, so two channels answering the same request cannot
silently replace a human's answer.
"""
import argparse
import datetime
import os
import sqlite3
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB = os.path.join(BASE, "shared", "applications.db")
ARTIFACTS = os.path.join(BASE, "shared", "build_artifacts")
# A plugin install can live anywhere; an explicit path always wins.
DB = os.environ.get("JOB_HUNTING_DB", DB)


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect():
    con = sqlite3.connect("file:" + DB + "?mode=rw", uri=True, timeout=15)
    con.row_factory = sqlite3.Row
    return con


def request_text(con, app_id):
    row = con.execute(
        "SELECT id, company, role_title, status, overall_match_score, "
        "keyword_match_score, title_displayed, approval_decision, "
        "approval_decided_at, sent_at, posting_url FROM applications WHERE id=?",
        (app_id,),
    ).fetchone()
    if row is None:
        print(f"ERROR: no application row for id={app_id}", file=sys.stderr)
        return None
    gaps = con.execute(
        "SELECT claim_text, missing_evidence FROM open_gaps WHERE application_id=? "
        "ORDER BY id", (app_id,),
    ).fetchall()
    lines = [
        f"APPROVAL NEEDED — App #{row['id']} · {row['company']} · {row['role_title']}",
        f"Status: {row['status']} | score: {row['overall_match_score']} | "
        f"keyword: {row['keyword_match_score']} | "
        f"title shown: {row['title_displayed'] or '(not set)'}",
        f"Posting: {row['posting_url']}",
    ]
    if gaps:
        lines.append("Honest gaps flagged by the risk gate:")
        for g in gaps:
            lines.append(f"  - {g['claim_text']}: {g['missing_evidence']}")
    else:
        lines.append("No open gaps recorded.")
    d = os.path.join(ARTIFACTS, f"app_{row['id']}")
    lines.append(f"Artifacts: {d}")
    if os.path.isdir(d):
        for name in ("resume_match.md", "risk_tactics_change_log.md",
                     "application_qa.md", "cover_letter.txt"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                lines.append(f"  - {name}")
    lines.append(
        "Reply APPROVE <id> to submit, or SKIP <id> to drop it. "
        "Record with: approval.py --record <id> --decision approve|skip --by <name>"
    )
    return "\n".join(lines)


def record(con, app_id, decision, who, note):
    con.execute("BEGIN IMMEDIATE")
    row = con.execute(
        "SELECT id, approval_decision, approval_decided_at, sent_at FROM applications WHERE id=?",
        (app_id,),
    ).fetchone()
    if row is None:
        con.rollback()
        print(f"ERROR: no application row for id={app_id}", file=sys.stderr)
        return 1
    if row["approval_decided_at"] is not None:
        con.rollback()
        print(
            f"REFUSED: app {app_id} already has a decision recorded at "
            f"{row['approval_decided_at']} ({row['approval_decision']!r}). "
            "A second answer must not silently replace a human's first one.",
            file=sys.stderr,
        )
        return 1
    now = utcnow()
    if decision == "approve" and row["sent_at"]:
        con.rollback()
        print(f"REFUSED: app {app_id} was already sent at {row['sent_at']}.",
              file=sys.stderr)
        return 1
    con.execute(
        "UPDATE applications SET approval_decision=?, approval_decided_at=?, "
        "status=CASE WHEN status='rejected_by_gate' THEN 'staged' ELSE status END "
        "WHERE id=?",
        (decision, now, app_id),
    )
    con.commit()
    shown = con.execute(
        "SELECT id, company, status, approval_decision, approval_decided_at "
        "FROM applications WHERE id=?", (app_id,),
    ).fetchone()
    print("RECORDED " + " | ".join(str(shown[k]) for k in
          ("id", "company", "status", "approval_decision", "approval_decided_at")))
    if note:
        print(f"NOTE (channel-side, not stored): {note}")
    print(f"BY: {who}")
    return 0


def list_pending(con):
    rows = con.execute(
        "SELECT id, company, role_title, status, overall_match_score "
        "FROM applications WHERE approval_decided_at IS NULL "
        "AND status IN ('staged', 'awaiting_approval') ORDER BY id"
    ).fetchall()
    if not rows:
        print("No application is waiting on a human decision.")
        return 0
    print(f"{len(rows)} application(s) waiting on a human decision:")
    for r in rows:
        print(f"  app {r['id']} | {r['company']} | {r['role_title']} | "
              f"{r['status']} | score {r['overall_match_score']}")
    return 0


def check(con, app_id):
    row = con.execute(
        "SELECT approval_decision, approval_decided_at, sent_at FROM applications WHERE id=?",
        (app_id,),
    ).fetchone()
    if row is None:
        print(f"BLOCKED: no application row for id={app_id}")
        return 1
    d = (row["approval_decision"] or "").strip().lower()
    if d not in ("approve", "approved"):
        print(f"BLOCKED: id={app_id} approval_decision={d or '(unset)'!r}")
        return 1
    if row["sent_at"]:
        print(f"BLOCKED: id={app_id} already sent at {row['sent_at']}")
        return 1
    print(f"ALLOWED: id={app_id} approved by a human at {row['approval_decided_at']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--request", type=int, metavar="APP_ID")
    ap.add_argument("--record", type=int, metavar="APP_ID")
    ap.add_argument("--decision", choices=("approve", "skip"))
    ap.add_argument("--by", help="the human who decided (mandatory)")
    ap.add_argument("--note", default="", help="channel-side context, not stored")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--check", type=int, metavar="APP_ID")
    args = ap.parse_args()

    if not any([args.request, args.record, args.list, args.check]):
        ap.error("nothing to do: pass --request, --record, --list or --check")
    con = connect()
    try:
        if args.request:
            print(request_text(con, args.request))
        elif args.record:
            if not args.decision:
                ap.error("--record needs --decision approve|skip")
            if not args.by:
                ap.error("--record needs --by <human name>")
            return record(con, args.record, args.decision, args.by, args.note)
        elif args.list:
            return list_pending(con)
        elif args.check:
            return check(con, args.check)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())