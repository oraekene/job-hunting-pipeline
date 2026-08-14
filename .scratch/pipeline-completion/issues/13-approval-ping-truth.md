# 13 — Approval ping truth: mark only a real Telegram send

**What to build:** The 2026-08-13 sweep recorded `approval_sent_at` for all
7 staged rows while delivering the approval digest only in the desktop chat
session — no Telegram message was ever sent to Kenechukwu. The timestamp is
the pipeline's "ping actually fired" marker, so it now lies. Fix: the
approval-submit protocol must treat a Telegram send (verified) as the only
thing that earns the mark, and the 7 false timestamps are cleared so the
approval queue is truthful again.

**Blocked by:** None — can start immediately

**Status:** done

- [x] `10-approval-and-submit/SKILL.md` states explicitly: the approval
  ping is a Telegram message send, not a digest in the running session's
  chat; a desktop/web session is not a delivery channel for this gate
- [x] The skill's mark step (step 4) requires the Telegram send to have
  succeeded (delivered, not just queued) before
  `pipeline_processor.py --mark-approval-pinged <id>` is called
- [x] One-off correction (documented): the 7 rows' `approval_sent_at`
  (apps 1, 2, 3, 4, 11, 12, 14) are reset to NULL, returning them to the
  approval queue
- [x] `--approval-queue` output after correction lists all 7 again
- [x] Orchestrator blueprint prompt reworded so "when the ping actually
  fires" means "after the Telegram message is sent", not "after the
  digest is printed"
