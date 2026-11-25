#!/usr/bin/env python3
"""Localhost control plane for the job-hunting skill package.

One file, standard library only (plus PyYAML, already required by the repo).
Lists every config file, every hardcoded code setting, every environment
variable and secret location, cron / scheduled-task state, and the SQLite
settings tables. Two write paths exist and only two: YAML and JSON config
files, each saved after an automatic backup.

Run:  python control-plane/serve.py [--port 8791] [--no-open]
Test: python control-plane/serve.py --selftest
"""

import argparse
import datetime as _dt
import json
import time
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INV_DIR = ROOT / ".scratch" / "control-plane"
BACKUPS = HERE / "backups"

# Folders that hold run output, not settings.
SKIP_DIRS = {
    "__pycache__", "build_artifacts", "company_research_cache", "node_modules",
    ".git", "cron_executions",
}
# Files that are run data, even though the extension looks like config.
SKIP_NAME = re.compile(r"\.(bak|raw|log)$", re.I)

MAX_FILE_BYTES = 400_000
SECRETISH = re.compile(r"TOKEN|SECRET|PASSWORD|PASSWD|API_KEY|CREDENTIAL|APP_PASSWORD", re.I)

ENV_PY = re.compile(
    r"os\.(?:environ\.get\(|environ\[|getenv\()\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']"
)
ENV_PS = re.compile(r"\$env:([A-Za-z_][A-Za-z0-9_]*)")
ENV_SH = re.compile(r"^[ \t]*export[ \t]+([A-Za-z_][A-Za-z0-9_]*)=", re.M)


TEXT_SUFFIX = {".yaml", ".yml", ".json", ".md"}


def _skip(rel):
    parts = rel.parts
    if set(parts) & SKIP_DIRS:
        return True
    # bundled virtualenvs are third-party code, not this project's settings
    return any(p.startswith(".venv") or p == "site-packages" for p in parts)


def _walk(exts):
    """Every repo file that is not run output.

    os.walk with directory pruning, not rglob: the bundle ships two virtualenvs
    with tens of thousands of third-party files, and walking into them costs
    tens of seconds per page load.
    """
    for dirpath, dirnames, filenames in os.walk(ROOT):
        base = Path(dirpath)
        rel_dir = base.relative_to(ROOT)
        dirnames[:] = sorted(d for d in dirnames if not _skip(rel_dir / d))
        for name in sorted(filenames):
            path = base / name
            rel = path.relative_to(ROOT)
            if _skip(rel) or SKIP_NAME.search(name):
                continue
            if path.suffix in {".db", ".sqlite"}:
                # a database is never size-capped: the real one is ~900 KB
                yield path
                continue
            try:
                if path.stat().st_size > MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            if name.startswith(".env") or path.suffix in exts or name.endswith(".template"):
                yield path


def _repo_files():
    return list(_walk(TEXT_SUFFIX))


def _kind(path):
    if path.suffix in {".db", ".sqlite"}:
        return "database"
    if path.name.startswith(".env"):
        return "secrets"
    if path.name.endswith(".template"):
        return "template"
    if path.suffix in {".yaml", ".yml"}:
        return "config"
    if path.suffix == ".json":
        return "config" if "cron" in str(path.parent).lower() or "cron" in path.name.lower() else "data"
    return "doc"


def discover_files():
    rows = []
    for path in _repo_files():
        try:
            size = path.stat().st_size
        except OSError:
            continue
        rows.append({
            "path": path.relative_to(ROOT).as_posix(),
            "kind": _kind(path),
            "bytes": size,
        })
    return rows


def read_file(rel):
    target = (ROOT / rel).resolve()
    if ROOT not in target.parents and target != ROOT:
        raise ValueError("path escapes the repo root")
    if not target.is_file():
        raise ValueError("not a file")
    # newline="" on both the read and the write so a save never rewrites CRLF as
    # LF or the reverse: this repo's YAML files are LF, and text mode would have
    # converted them on the way out
    raw = open(target, "r", encoding="utf-8", errors="replace", newline="").read()
    parsed = None
    if target.suffix in {".yaml", ".yml"} or target.name.endswith(".template"):
        try:
            parsed = yaml.safe_load(raw)
        except Exception as exc:  # a broken YAML must still be visible
            parsed = {"_yaml_error": str(exc)}
    elif target.suffix == ".json":
        try:
            parsed = json.loads(raw)
        except Exception as exc:
            parsed = {"_json_error": str(exc)}
    return raw, parsed


def save_file(rel, content):
    """Write only YAML/JSON config files, and always keep a backup."""
    target = (ROOT / rel).resolve()
    if ROOT not in target.parents and target != ROOT:
        raise ValueError("path escapes the repo root")
    if target.suffix not in {".yaml", ".yml", ".json"} and not target.name.endswith(".template"):
        raise ValueError("only YAML and JSON config files are writable")
    if target.suffix in {".json"} and "cron" not in str(target).lower():
        raise ValueError("only cron JSON files are writable")
    try:
        parsed = yaml.safe_load(content) if target.suffix in {".yaml", ".yml"} or target.name.endswith(".template") else json.loads(content)
    except Exception as exc:
        raise ValueError("refusing to save unparseable content: " + str(exc))
    if parsed is None:
        raise ValueError("refusing to save an empty document")
    BACKUPS.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = BACKUPS / (stamp + "-" + target.name + ".bak")
    if target.exists():
        shutil.copy2(target, backup)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        handle.write(content)
    os.replace(tmp, target)
    return backup.name


def parse_markdown_tables(md_path):
    """Turn the inventory markdown tables into rows, keeping the columns."""
    sections, heading, columns, rows = [], md_path.stem, [], []
    text = md_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        if line.startswith("## "):
            if rows:
                sections.append({"heading": heading, "columns": columns, "rows": rows})
            heading, columns, rows = line[3:].strip(), [], []
            continue
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if set("".join(cells)) <= set("-: "):
            continue
        if not columns:
            columns = cells
            continue
        # a literal pipe inside a cell must not silently drop the whole row
        cells = (cells + [""] * len(columns))[: len(columns)]
        rows.append(dict(zip(columns, cells)))
    if rows:
        sections.append({"heading": heading, "columns": columns, "rows": rows})
    return sections


def load_inventories():
    out = []
    if INV_DIR.is_dir():
        for path in sorted(INV_DIR.glob("*.md")):
            out.append({"file": path.name, "sections": parse_markdown_tables(path)})
    return out


def env_usage():
    """Every environment variable name any file in the repo reads."""
    usage = {}
    for path in _walk({".py", ".ps1", ".cmd", ".sh", ".md", ".yaml", ".yml"}):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if len(text) > MAX_FILE_BYTES:
            continue
        rel = path.relative_to(ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), 1):
            if path.name.startswith(".env"):
                assigned = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=", line)
                if assigned:
                    usage.setdefault(assigned.group(1), []).append(rel + ":" + str(line_no))
                continue
            if not any(t in line for t in ("environ", "getenv", "$env:", "export ", "os.environ")):
                continue
            for pattern in (ENV_PY, ENV_PS, ENV_SH):
                for name in pattern.findall(line):
                    usage.setdefault(name, []).append(rel + ":" + str(line_no))
    rows = []
    for name, sources in sorted(usage.items()):
        rows.append({
            "name": name,
            "sources": sources,
            "secret": bool(SECRETISH.search(name)),
            "state": "SET" if os.environ.get(name) else "unset",
        })
    return rows


def db_state():
    dbs = [p for p in _repo_files() if _kind(p) == "database"]
    out = []
    for path in dbs:
        rel = path.relative_to(ROOT).as_posix()
        try:
            uri = "file:" + str(path.resolve()).replace("\\", "/") + "?mode=ro"
            con = sqlite3.connect(uri, uri=True)
            tables = [r[0] for r in con.execute(
                "select name from sqlite_master where type=" + chr(39) + "table" + chr(39) + " order by name")]
            info = []
            if not tables:
                out.append({"file": rel, "tables": [],
                            "note": "empty database file, 0 tables"})
                con.close()
                continue
            for table in tables:
                try:
                    count = con.execute("select count(*) from " + chr(34) + table + chr(34)).fetchone()[0]
                    cols = [r[1] for r in con.execute("pragma table_info(" + chr(34) + table + chr(34) + ")")]
                    rows = []
                    if count <= 500:
                        rows = [dict(zip(cols, r)) for r in con.execute(
                            "select * from " + chr(34) + table + chr(34) + " limit 200")]
                    info.append({"table": table, "rows": count, "columns": cols, "contents": rows})
                except sqlite3.Error:
                    continue
            con.close()
        except sqlite3.Error as exc:
            out.append({"file": rel, "error": str(exc)})
            continue
        out.append({"file": rel, "tables": info})
    return out


def cron_live():
    """The live job list.

    This bundle's cron is Hermes-internal, not the Windows Task Scheduler, so
    schtasks finds nothing here; `hermes cron list` is the real source.
    """
    try:
        proc = subprocess.run(["hermes", "cron", "list"], capture_output=True,
                              text=True, errors="replace", timeout=180)
    except Exception as exc:
        return {"error": str(exc)}
    lines = proc.stdout.splitlines()
    active = sum(1 for line in lines if "[active]" in line)
    return {"job_count": active, "jobs": lines[-20000:],
            "note": "live hermes cron list (%d active jobs)" % active}


def hooks_live():
    """The two security hooks that enforce Rule 1 and DB ownership."""
    out = {}
    for name, args in (("list", ["hermes", "hooks", "list"]),
                       ("doctor", ["hermes", "hooks", "doctor"])):
        try:
            proc = subprocess.run(args, capture_output=True, text=True,
                                  errors="replace", timeout=180)
            out[name] = proc.stdout[-20000:] + (proc.stderr[-4000:] if proc.stderr else "")
        except Exception as exc:
            out[name] = str(exc)
    return out


RULES_FILES = [
    "shared/pipeline-rules.md",
    "shared/pipeline-rules-addendum.md",
    "security/security-setup.md",
]


def rules_index():
    """Gates and rules that exist only as prose, by heading, kept searchable."""
    rows = []
    for rel in RULES_FILES:
        path = ROOT / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for chunk in re.split(r"\n(?=## )", text):
            match = re.match(r"## (.+)", chunk)
            if not match:
                continue
            heading = match.group(1).strip()
            body = chunk.split("\n", 1)[1].strip()
            if not body:
                continue
            rows.append({"source": rel, "heading": heading,
                         "chars": len(body), "body": body[:6000]})
    return rows


def _run(args, cwd):
    try:
        proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                              errors="replace", timeout=180)
    except Exception as exc:
        return {"error": str(exc)}
    return {"command": " ".join(str(a) for a in args), "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:], "stderr": proc.stderr[-4000:]}


def cron_health():
    """Reuse the two existing read-only CLIs rather than reimplementing them."""
    return {
        "executions": _run([sys.executable, str(ROOT / "cron" / "executions.py"),
                             "--db", str(ROOT / "shared" / "applications.db"), "report"],
                            cwd=str(ROOT / "cron")),
        "drift": _run([sys.executable, str(ROOT / "cron" / "scripts" / "verify-cron-config.py")],
                      cwd=str(ROOT / "cron" / "scripts")),
    }


CACHE_TTL = 20
_cache = {"built": 0.0, "data": None}
_build_lock = threading.Lock()


def snapshot(force=False):
    """Everything the page shows.

    A full build walks the tree, reads the database and runs two cron CLIs, which
    takes tens of seconds on this machine. So the page never waits for one: it
    renders whatever the cache holds (or "building"), and a force rebuild happens
    in the background. The refresh button calls /api/data?force=1.
    """
    if not force:
        if _cache["data"] is not None and time.time() - _cache["built"] < CACHE_TTL:
            return _cache["data"]
        return _cache["data"] or {"building": True}
    if not _build_lock.acquire(blocking=False):
        return _cache["data"] or {"building": True}
    try:
        data = {
            "generated_at": _dt.datetime.now().isoformat(timespec="seconds"),
            "root": str(ROOT),
            "files": discover_files(),
            "inventory": load_inventories(),
            "env": env_usage(),
            "databases": db_state(),
            "cron": cron_live(),
            "hooks": hooks_live(),
            "rules": rules_index(),
            "cron_health": cron_health(),
            "writable": "YAML config files and cron JSON only; every save keeps a backup.",
        }
        _cache["built"] = time.time()
        _cache["data"] = data
    finally:
        _build_lock.release()
    return _cache["data"] or {"building": True}


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>job-hunting control plane</title>
<style>
:root { color-scheme: light dark; }
body { font: 14px/1.45 system-ui, sans-serif; margin: 0; display: flex; height: 100vh; }
nav { width: 250px; padding: 12px; border-right: 1px solid #8884; overflow: auto; }
nav a { display: block; padding: 4px 0; cursor: pointer; color: inherit; text-decoration: none; }
nav a:hover { text-decoration: underline; }
main { flex: 1; padding: 12px 18px; overflow: auto; }
input#q { width: 100%; box-sizing: border-box; padding: 6px; margin-bottom: 10px; }
table { border-collapse: collapse; width: 100%; margin: 6px 0 16px; }
td, th { border: 1px solid #8883; padding: 3px 6px; text-align: left; vertical-align: top; }
details { margin-bottom: 8px; }
summary { cursor: pointer; font-weight: 600; }
textarea { width: 100%; height: 320px; font: 12px/1.4 ui-monospace, monospace; box-sizing: border-box; }
button { margin: 4px 4px 4px 0; }
.muted { opacity: .65; }
.warn { background: #a002; padding: 6px; border-left: 3px solid #a00; }
.tag { border: 1px solid #8886; border-radius: 4px; padding: 0 4px; font-size: 11px; }
</style></head><body>
<nav id="toc"></nav>
<main>
<div class="warn">This page is bound to 127.0.0.1 only. Secret values are hidden until you click reveal,
and the page is never served to the network.</div>
<p class="muted" id="meta"></p>
<input id="q" placeholder="filter everything by file, name, value or setting">
<button onclick="reload(true)">refresh data</button>
<label class="muted"><input type="checkbox" id="showall"> docs and data dumps too (hidden by default)</label>
<div id="root"></div>
</main>
<script>
const ESCMAP = {'&': '&' + 'amp;', '<': '&' + 'lt;', '>': '&' + 'gt;', '"': '&' + 'quot;'};
const esc = s => String(s).replace(/[&<>"]/g, c => ESCMAP[c]);
let DATA = null, FILTER = '', SHOWALL = false;
// a cell prefixed with RAW: is already safe HTML and must not be escaped
const cell = c => '<td>' + (c === null || c === undefined ? '' :
  (String(c).startsWith('RAW:') ? String(c).slice(4) : esc(c))) + '</td>';
const row = (cells) => '<tr>' + cells.map(cell).join('') + '</tr>';
const head = (cols) => '<tr>' + cols.map(c => '<th>' + esc(c) + '</th>').join('') + '</tr>';
const table = (cols, rows) => '<table><thead>' + head(cols) + '</thead><tbody>' +
  rows.map(r => row(cols.map(c => c === null ? r : r[c]))).join('') + '</tbody></table>';
const hit = (text) => !FILTER || String(text).toLowerCase().includes(FILTER);

function section(id, title, body) {
  const el = document.createElement('section');
  el.id = id;
  el.innerHTML = '<h2>' + esc(title) + '</h2>' + body;
  document.getElementById('root').appendChild(el);
  const a = document.createElement('a');
  a.textContent = title; a.href = '#' + id; a.onclick = () => el.scrollIntoView();
  document.getElementById('toc').appendChild(a);
  return el;
}

function render() {
  document.getElementById('root').innerHTML = '';
  document.getElementById('toc').innerHTML = '';
  document.getElementById('meta').textContent =
    DATA.generated_at + '  |  ' + DATA.root + '  |  ' + DATA.files.length + ' files  |  ' +
    DATA.env.length + ' env vars  |  ' + DATA.writable;

  section('env', 'Environment variables (' + DATA.env.length + ')',
    table(['name', 'secret', 'state', 'read by'],
      DATA.env.filter(e => hit([e.name, e.sources.join(' ')].join(' '))).map(e => ({
        name: 'RAW:' + esc(e.name) + (e.secret && e.state === 'SET'
          ? ' <button onclick="reveal(\\'' + esc(e.name) + '\\')">reveal</button>' : ''),
        secret: e.secret ? 'yes' : 'no', state: e.state, sources: e.sources.join(', ')
      }))));

  const inv = section('inv', 'Code settings registry (hardcoded, from inventory markdown)', '');
  DATA.inventory.forEach(inv_file => {
    const d = document.createElement('details'); d.open = inv_file.file.includes('-a');
    d.innerHTML = '<summary>' + esc(inv_file.file) + '</summary>';
    inv_file.sections.forEach(sec => {
      const visible = sec.rows.filter(r => hit([sec.heading, sec.columns, JSON.stringify(r)].join(' ')));
      if (!visible.length) return;
      const h = document.createElement('div');
      h.innerHTML = '<h3>' + esc(sec.heading) + ' (' + visible.length + ' of ' + sec.rows.length + ')</h3>' +
        table(sec.columns, visible.map(r => {
          const o = {}; sec.columns.forEach(c => o[c] = r[c]); return o;
        }));
      d.appendChild(h);
    });
    inv.appendChild(d);
  });

  const files = section('files', 'Config files (' + DATA.files.length + ')', '');
  DATA.files.filter(f => (SHOWALL || f.kind === 'config' || f.kind === 'template' ||
    f.kind === 'database' || f.kind === 'secrets') && hit([f.path, f.kind].join(' '))).forEach(f => {
    const d = document.createElement('details');
    const editable = f.kind === 'config' && (f.path.endsWith('.yaml') || f.path.endsWith('.yml') ||
      f.path.endsWith('.template') || f.path.endsWith('.json'));
    d.dataset.path = f.path;
    d.innerHTML = '<summary>' + esc(f.path) + '  <span class="tag">' + esc(f.kind) + '</span>' +
      ' <span class="muted">' + f.bytes + ' bytes</span>' +
      (editable ? ' <button onclick="edit(\\'' + esc(f.path) + '\\')">edit</button>' : '') +
      (f.kind === 'config' ? ' <button onclick="view(\\'' + esc(f.path) + '\\')">values</button>' : '') + '</summary>' +
      '<div class="body"></div>';
    files.appendChild(d);
  });

  section('db', 'Databases', DATA.databases.map(db => {
    if (db.error) return '<p>' + esc(db.file) + ': ' + esc(db.error) + '</p>';
    if (db.note) return '<p>' + esc(db.file) + ': ' + esc(db.note) + '</p>';
    return '<details><summary>' + esc(db.file) + ' (' + db.tables.length + ' tables)</summary>' +
      table(['table', 'rows', 'columns', 'contents'], db.tables.map(t => ({
        table: t.table, rows: t.rows, columns: t.columns.join(', '),
        contents: t.contents.length ? 'RAW:<pre>' + esc(JSON.stringify(t.contents, null, 1)) + '</pre>' : '(large, rows hidden)'
      }))) + '</details>';
  }).join(''));

  section('cron', 'Live cron jobs (hermes cron list)',
    '<p>' + esc(DATA.cron.note || DATA.cron.error || '') + '</p>' +
    (DATA.cron.jobs || []).map(t => '<pre>' + esc(t) + '</pre>').join(''));

  section('hooks', 'Security hooks (Rule 1 submit gate, db ownership)',
    Object.keys(DATA.hooks || {}).map(k =>
      '<details><summary>' + esc(k) + '</summary><pre>' + esc(DATA.hooks[k]) + '</pre></details>').join(''));

  section('health', 'Cron health (live CLI reports)', ['executions', 'drift'].map(key => {
    const r = DATA.cron_health[key];
    if (r.error) return '<p>' + esc(key) + ': ' + esc(r.error) + '</p>';
    return '<details><summary>' + esc(key) + ' — exit ' + esc(r.returncode) +
      ' <span class="muted">' + esc(r.command) + '</span></summary>' +
      '<pre>' + esc(r.stdout || '') + (r.stderr ? '\\nstderr:\\n' + esc(r.stderr) : '') + '</pre></details>';
  }).join(''));

  section('rules', 'Gates and rules in prose (' + DATA.rules.length + ')',
    table(['source', 'rule / gate', 'text'],
      DATA.rules.filter(r => hit([r.source, r.heading, r.body].join(' '))).map(r => ({
        source: r.source, heading: r.heading,
        text: 'RAW:<details><summary>' + esc(r.chars) + ' chars</summary><pre>' +
          esc(r.body) + '</pre></details>'
      }))));
}

async function api(url, opts) {
  const r = await fetch(url, opts);
  const body = await r.json();
  if (!r.ok) { alert(body.error || r.statusText); throw new Error(body.error); }
  return body;
}
const boxFor = rel => [...document.querySelectorAll('#files details')].find(d => d.dataset.path === rel);
async function view(rel) {
  const data = await api('/api/file?path=' + encodeURIComponent(rel));
  boxFor(rel).querySelector('.body').innerHTML = data.parsed
    ? '<pre>' + esc(JSON.stringify(data.parsed, null, 2)) + '</pre><details><summary>raw</summary><pre>' +
      esc(data.raw) + '</pre></details>'
    : '<pre>' + esc(data.raw) + '</pre>';
}
async function edit(rel) {
  const data = await api('/api/file?path=' + encodeURIComponent(rel));
  boxFor(rel).querySelector('.body').innerHTML =
    '<textarea></textarea><button onclick="save(\\'' + esc(rel) + '\\')">save</button>' +
    '<span class="muted">parse-checked before write; backup kept</span>';
  boxFor(rel).querySelector('textarea').value = data.raw;
}
async function save(rel) {
  const box = boxFor(rel);
  const content = box.querySelector('textarea').value;
  const res = await api('/api/file?path=' + encodeURIComponent(rel), {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({content})});
  box.querySelector('.body').innerHTML = '<p class="muted">saved. backup: ' + esc(res.backup) + '</p>';
}
async function reveal(name) {
  const data = await api('/api/secret?name=' + encodeURIComponent(name));
  alert(data.value || '(unset)');
}
document.getElementById('q').oninput = e => { FILTER = e.target.value.toLowerCase(); render(); };
document.getElementById('showall').onchange = e => { SHOWALL = e.target.checked; render(); };
async function reload(force) {
  const b = document.querySelector('button[onclick="reload(true)"]');
  b.textContent = 'loading...';
  DATA = await api('/api/data' + (force ? '?force=1' : ''));
  b.textContent = DATA.building ? 'building...' : 'refresh data';
  if (DATA.building) { setTimeout(() => reload(false), 2000); return; }
  render();
}
(async () => { DATA = await api('/api/data');
  if (DATA.building) { setTimeout(() => reload(false), 2000); } else { render(); } })();
</script></body></html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "job-hunting-control-plane/1"

    def _send(self, code, body, ctype="application/json"):
        payload = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            return self._send(200, PAGE, "text/html")
        if url.path == "/api/data":
            force = parse_qs(url.query).get("force", [""])[0] == "1"
            return self._send(200, json.dumps(snapshot(force=force)))
        if url.path == "/api/file":
            rel = parse_qs(url.query).get("path", [""])[0]
            try:
                raw, parsed = read_file(rel)
            except Exception as exc:
                return self._send(400, json.dumps({"error": str(exc)}))
            return self._send(200, json.dumps({"path": rel, "raw": raw, "parsed": parsed}))
        if url.path == "/api/secret":
            name = parse_qs(url.query).get("name", [""])[0]
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                return self._send(400, json.dumps({"error": "bad name"}))
            return self._send(200, json.dumps({"name": name, "value": os.environ.get(name, "")}))
        return self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/api/file":
            return self._send(404, json.dumps({"error": "not found"}))
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
            rel = parse_qs(urlparse(self.path).query).get("path", [""])[0]
            backup = save_file(rel, body["content"])
        except Exception as exc:
            return self._send(400, json.dumps({"error": str(exc)}))
        return self._send(200, json.dumps({"ok": True, "backup": backup}))


def selftest():
    # a raw newline inside a JS string literal breaks the page silently, so
    # parse the embedded script with node when node is available
    script = PAGE.split("<script>", 1)[1].split("</script>", 1)[0]
    node = shutil.which("node")
    if node:
        tmp = HERE / "_pagecheck.js"
        tmp.write_text(script, encoding="utf-8")
        proc = subprocess.run([node, "--check", str(tmp)], capture_output=True, text=True)
        tmp.unlink()
        assert proc.returncode == 0, "inline page JS does not parse:\n" + proc.stderr
    files = discover_files()
    inv = load_inventories()
    inv_rows = sum(len(s["rows"]) for f in inv for s in f["sections"])
    envs = env_usage()
    dbs = db_state()
    tables = sum(len(d.get("tables", [])) for d in dbs)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = server.server_address[1]
    import urllib.request
    with urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=10) as r:
        assert r.status == 200 and b"control plane" in r.read()
    with urllib.request.urlopen("http://127.0.0.1:%d/api/data?force=1" % port, timeout=180) as r:
        data = json.loads(r.read())
    server.shutdown()
    assert data["files"], "no config files discovered"
    assert data["rules"], "no rules parsed"
    assert data["hooks"]["list"], "hooks list empty"
    assert data["cron_health"]["executions"].get("stdout"), "executions report empty"
    assert len(envs) >= 5, "too few env vars found: %d" % len(envs)
    assert tables >= 30, "too few db tables: %d" % tables
    assert inv_rows >= 20, "inventory markdown parsed %d rows" % inv_rows
    print("selftest ok: %d files, %d rules, %d inventory rows, %d env vars, %d db tables"
          % (len(files), len(data["rules"]), inv_rows, len(envs), tables))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8791)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = "http://127.0.0.1:%d/" % args.port
    print("control plane: " + url + "  (ctrl+c to stop)")
    threading.Thread(target=snapshot, args=(True,), daemon=True).start()
    if not args.no_open:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)