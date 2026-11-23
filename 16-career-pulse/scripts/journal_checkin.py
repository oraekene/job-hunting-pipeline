#!/usr/bin/env python3
"""16-career-pulse: journal check-in.

Sends a low-key rotation prompt to Kenechukwu via Telegram, then polls the
gateway's message store (state.db) for his reply.  When a reply lands, the
raw text is written to career_journal and candidate facts are flagged for
07-context-architect.

Usage (from cron agent / desktop agent):
    python journal_checkin.py [--poll-seconds N] [--dry-run]

The script reads the Telegram bot token and home-channel chat_id from
.hermes/.env (via the same resolution hermes send uses) so credentials are
never echoed.
"""
import argparse, json, os, sqlite3, time, urllib.parse, urllib.request, sys


def resolve_hermes_home():
    """Find Hermes' home without tying the script to one user's machine."""
    for variable, suffix in (("HERMES_HOME", ""), ("LOCALAPPDATA", "hermes")):
        base = os.environ.get(variable, "").strip()
        if base:
            return os.path.join(base, suffix)
    return os.path.expanduser("~/.hermes")


HERMES_HOME = resolve_hermes_home()
ENV_PATH = os.path.join(HERMES_HOME, ".env")
DB_PATH = os.path.join(HERMES_HOME, "state.db")
APPS_DB = os.path.join(HERMES_HOME, "skills", "job-hunting", "shared", "applications.db")

# Prompt rotation — first entry when career_journal is empty.
PROMPTS = [
    "Weekly journal check-in — what got hard this week?",
    "Quick check-in — what got resolved this week?",
    "What shipped this week, even a small win?",
    "Who did you work with this week and how did it go?",
    "What would you do differently, looking back?",
]


def load_env():
    """Load .env key=value pairs into a dict (does NOT touch os.environ)."""
    env = {}
    if not os.path.exists(ENV_PATH):
        return env
    with open(ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip("'\"")
    return env


def telegram_request(token, method, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _resolve_telegram_session_id(db, session_key):
    """Look up the session_id that gateway_routing maps a telegram DM key to.

    gateway_routing stores session_id inside the JSON entry_json column.
    """
    conn = sqlite3.connect(db)
    try:
        r = conn.execute(
            "SELECT entry_json FROM gateway_routing WHERE session_key=?", (session_key,)
        ).fetchone()
        if not r:
            return None
        entry = json.loads(r[0])
        return entry.get("session_id")
    finally:
        conn.close()


def current_max_msg_id(db, session_id):
    conn = sqlite3.connect(db)
    try:
        r = conn.execute(
            "SELECT MAX(id) as m FROM messages WHERE session_id=?", (session_id,)
        ).fetchone()
        return r[0] or 0
    finally:
        conn.close()


def wait_for_reply(db, session_key, baseline_id, timeout):
    """Poll state.db messages table for a new user message from Kenechukwu."""
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = conn.execute(
            "SELECT id, substr(content,1,65536) as content, timestamp FROM messages "
            "WHERE session_id=? AND role='user' AND id > ? "
            "ORDER BY id ASC LIMIT 1",
            (session_key, baseline_id),
        ).fetchall()
        if rows:
            conn.close()
            return rows[0]["content"], rows[0]["timestamp"]
        time.sleep(2)
    conn.close()
    return None, None


def pick_prompt(db_path):
    """Rotate prompts based on the last entry_at in career_journal."""
    conn = sqlite3.connect(db_path)
    try:
        r = conn.execute(
            "SELECT raw_text, entry_at FROM career_journal ORDER BY entry_at DESC LIMIT 1"
        ).fetchone()
        idx = 0 if not r else (1 if r[0] else 0)  # simplified: cycle by count
        # Actually: count entries to determine rotation position
        n = conn.execute("SELECT COUNT(*) FROM career_journal WHERE deleted_at IS NULL").fetchone()[0]
        idx = n % len(PROMPTS) if n > 0 else 0
        return PROMPTS[idx], n
    finally:
        conn.close()


def store_journal_entry(db_path, raw_text, candidate_facts, session_key):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO career_journal (entry_at, raw_text, candidate_facts_extracted, "
            "surfaced_to_context_architect, surfaced_at) VALUES (datetime('now'), ?, ?, 0, NULL)",
            (raw_text, json.dumps(candidate_facts) if candidate_facts else None),
        )
        conn.commit()
        entry_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return entry_id
    finally:
        conn.close()


def extract_candidate_facts(raw_text):
    """Flag durable facts containing numbers/dates/percentages for context-architect.

    Qualitative content is left as raw recall; anything with a figure gets
    echoed back for explicit confirmation (voice-interview-mode safeguard).
    """
    import re
    facts = []
    # Split into sentences and flag those containing numbers, dates, or percentages.
    sentences = re.split(r'(?<=[.!?])\s+', raw_text.strip())
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if re.search(r'\d{4}|\d+%|\b\d+\b', s):
            facts.append({"text": s, "category": "fact_with_figure"})
        elif re.search(r'\b(?:shipped|completed|resolved|built|launched|started|finished|deployed|led|migrated)\b',
                       s, re.I):
            facts.append({"text": s, "category": "status_change"})
    return facts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--poll-seconds", type=int, default=90)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN")
    chat_id = env.get("TELEGRAM_HOME_CHANNEL") or env.get("TELEGRAM_ALLOWED_USERS")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_HOME_CHANNEL not found in .env", file=sys.stderr)
        return 1

    # The gateway stores incoming Telegram DM replies under the session_id that
    # gateway_routing maps the telegram DM session_key to.  Look it up so we
    # poll the right rows.
    session_key = "agent:main:telegram:dm:" + str(chat_id).replace("-", "")
    target_session_id = _resolve_telegram_session_id(DB_PATH, session_key)
    if not target_session_id:
        print(f"WARNING: no gateway_routing row for {session_key}; "
              "incoming replies may not be stored. Using chat_id as fallback.", file=sys.stderr)
        target_session_id = session_key

    prompt, entry_count = pick_prompt(APPS_DB)
    print(f"Rotation: entry #{entry_count} -> prompt: {prompt}")

    # Record current message baseline so we only pick up NEW replies.
    baseline = current_max_msg_id(DB_PATH, target_session_id)
    print(f"Baseline max message id in telegram session: {baseline}")

    if a.dry_run:
        print(f"[DRY RUN] Would send to telegram:{chat_id}: {prompt}")
        print(f"[DRY RUN] Would poll for {a.poll_seconds}s for a reply")
        return 0

    # --- Send the prompt ---
    try:
        result = telegram_request(token, "sendMessage", chat_id=chat_id,
                                  text=prompt, disable_notification=False)
        if not result.get("ok"):
            print(f"ERROR sending telegram message: {result}", file=sys.stderr)
            return 2
        msg = result.get("result", {})
        print(f"Sent telegram message id={msg.get('message_id')} to chat_id={chat_id}")
    except Exception as e:
        print(f"ERROR sending telegram message: {e}", file=sys.stderr)
        return 2

    # --- Poll for a reply ---
    reply, ts = wait_for_reply(DB_PATH, target_session_id, baseline, a.poll_seconds)
    if reply is None:
        print(f"No reply within {a.poll_seconds}s. Prompt was sent; response pending.")
        return 0  # success — prompt sent, awaiting response

    print(f"Received reply: {reply[:200]}...")
    facts = extract_candidate_facts(reply)
    entry_id = store_journal_entry(APPS_DB, reply, facts, session_key)
    print(f"Stored journal entry #{entry_id} in career_journal")
    if facts:
        print(f"Flagged {len(facts)} candidate fact(s) for 07-context-architect:")
        for f in facts:
            print(f"  [{f['category']}] {f['text'][:120]}")
    else:
        print("No candidate facts flagged (qualitative content, no figures).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
