# pipeline_processor.py — parsing contracts (verified Aug 2026, app_18 build)

Source: `../../00-orchestrator/scripts/pipeline_processor.py` (from
`job-hunting-artifact-qa/references/`).
All behaviors below were confirmed by reading the source and by simulating the
parsers against app_15/app_16/app_18 artifacts. The processor NEVER computes
Gate 1 — it records what the artifacts say; the artifacts are the contract.

## Score extraction

### `count_resume_match_score(resume_match_path)`
```python
m = re.search(r"(\d+)%", text)   # FIRST percentage in the whole file
```
- Stored as DB `overall_match_score`.
- Convention (app_15, app_18): `## Overall Match Score: 73% raw / 55% with
  seniority penalty` → stored value = **73 (the raw number)**.
- **Trap:** for Senior-titled roles the raw score can pass `match_score.minimum`
  while the penalized score fails. The markdown's Gate 1 verdict is what humans
  and the approval gate read — it MUST state the penalized basis
  ("Score (55% penalized) < minimum (65) — [FAILED]").
- Nothing else in the file may contain a `%` before the header line.

### `count_keyword_score(keyword_json_path)`
```python
analysis = kw.get("analysis") or {}
score = analysis.get("match_score_percentage", kw.get("match_score_percentage", 0))
```
- **Nested `analysis.match_score_percentage` is canonical.** Top-level is a
  legacy fallback that "landed 0.0 for every stage-4 output" previously — always
  nest it.

## Gate 2 verdict — `read_overqualification_gate(rm_path)`

```python
m = re.search(r"Gate\s*2[^\n]*?verdict[^\n]*?:\s*([^\\n]+)", text, re.I)
raw = m.group(1).strip().strip("*").strip().lower()
normalize = {"passed": "clean", "clean": "clean", "flagged": "flagged",
             "dropped": "dropped", "skipped": "skipped"}
# substring match: "passed" in "**[PASSED]** — not overqualified..." → 'clean'
```
- Write: `**Gate 2 verdict**: [PASSED] — not overqualified. ...` → DB `clean`.
- Special case: a verdict containing "not applicable" + ("opposite" | "not
  overqualified" | "under") also maps to `clean` (under-scope is the opposite of
  overqualification → not a Gate 2 fail).
- If no Gate 2 line exists → NULL (never fabricated).

## Displayed title — `read_displayed_title(rcl_path)`

```python
sec = re.search(r"##\s*Tactic\s*2.*?(?=^##\s*Tactic|\Z)", text, re.S | re.M)
for line in sec.group(0).splitlines():
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) >= 2 and cells[1] not in ("", "-", "---", "Displayed Title"):
        return cells[1]
```
- Tactic 2 table header MUST be exactly:
  `| Original Title | Displayed Title | Evidence | Status |`
- First data row's 2nd cell is the recorded displayed title. Strict-mode rule:
  keep the held title (e.g. "Product Manager"), never a Senior/Principal variant.

## Risk-gate counts — `count_risk_gate(gate_log_path)`

```python
PASS_RE = re.compile(r"\[PASS\]")
FAIL_RE = re.compile(r"\[FAIL\]")
BORDERLINE_RE = re.compile(r"\[BORDERLINE PASS\]")
CORRECTED_RE = re.compile(r"\[CORRECTED\]")
UNVERIFIED_RE = re.compile(r"\[UNVERIFIED\]")
risk_pass = n_pass + n_borderline + n_corrected
risk_fail = n_fail
```
- Counts scan the WHOLE file, including the "## Final counts" summary lines
  (`- [PASS]: 9` matches `[PASS]`), so each declared count adds a phantom +1.
  Expected behavior — keep the bracket format for convention consistency.
- `[PASS]` does NOT match inside `[BORDERLINE PASS]` (space before "PASS").
- `[BORDERLINE PASS]` — note there is no space between PASS and the bracket.

## open_gaps extraction — `extract_gaps_from_risk_log(...)`

Two accepted forms:
1. One line, em-dash separated:
   `[FAIL] <claim> — <missing evidence>` matched by
   `r"\[FAIL\]\s*(?!:)(.+?)\s*—\s*(.+?)(?=\n|$)"`
   - The claim must NOT contain an em-dash before the separator (non-greedy
     match stops at the first `—`). Use en-dashes/commas inside claims.
   - Evidence may contain further em-dashes (captured to end of line).
2. `### [FAIL] <claim>` (or `- [FAIL] <claim>`) with a `Missing evidence:` /
   `evidence:` line within the next 3 lines.
- Summary lines like `[FAIL]: 8` are never extracted (`(?!:)` negative
  lookahead). Each parsed FAIL becomes an `open_gaps` DB row at commit time —
  artifacts-only builds record gaps via these log lines, no DB write needed.

## Artifact set

`verify_artifacts(app_id)` requires all 8 stage outputs present and non-empty:
`jd_analysis.md`, `resume_match.md`, `keyword_analysis.json`,
`resume_change_log.md`, `risk_tactics_change_log.md`, `cover_letter.txt`,
`application_qa.md`, `generate_resume.py` (+ `tailored_resume.docx` produced by
the script).

## Cover-letter word count — `count_cover_letter_words`

Body = all non-empty lines EXCEPT those starting with the signature name
("Kenechukwu"). Count = `len(body.split())`. Must be < 400.

## Senior-role scoring worked examples

- app_15 Camunda (Senior, foreign domain): raw 46 → penalized
  `round(46*0.75)=34` → below stretch floor 50 → clean no-stage.
- app_18 Toggl (Senior, AI-fluency-mandatory): keyword math
  7×3+5×2+2×1 = 33 possible; 6×3+2×2+2×1 = 24 earned → raw
  `round(24/33*100)=73` (Good) → penalized `round(73*0.75)=55` → in the
  50–65 stretch band → `[STRETCH]` human-review territory, Gate 1 [FAILED]
  vs minimum 65.
- Penalized score is what the Gate 1 verdict cites; raw is what the processor
  stores as `overall_match_score`. Keep both visible in the header line.

## Calibration constants (shared/dynamic-target-calibration.yaml, 2026-08)

`match_score.minimum: 65`, `stretch.floor: 50`, `stretch.enabled: true` →
50–65 = `[STRETCH]` band. `overqualification_tolerance: balanced`.
