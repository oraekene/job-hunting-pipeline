# Canonical Verifier Broken → Ad-hoc Replica Recipe (app_22, 2026-08-17)

## The bug (verify BEFORE debugging your artifacts)
`../scripts/verify_app_artifacts.py` cannot run on ANY app dir as shipped: it defines
`def check(cond, msg, fails)` (3 args) but every call site passes 2 args →
`TypeError: check() missing 1 required positional argument: 'fails'` at its very
first check (`analysis.total_keywords_found present`). Pre-existing — NOT caused
by any artifact set. If this fires, the script itself is the failure; do not
start re-auditing your JSON/markdown.

## Working fallback (verified end-to-end on app_22)
Replicate the same 5 checks in an ad-hoc script under the OS temp dir, run it,
clean it up. One-shot pattern that worked from `execute_code`:

1. Create the verifier with `tempfile.mkstemp(prefix="hermes-verify-", suffix=".py")`
   (OS temp dir; on Windows that resolves under `C:\Users\<user>\AppData\Local\Temp`).
2. The replica implements the canonical checks:
   (a) `keyword_analysis.json` — required analysis keys; keyword count in [10,15];
   every keyword has the 5 schema fields; per-keyword sanity (category in
   {Hard Skill, Domain Concept, Soft Skill}, weight in {1,2,3}, bool flag,
   non-empty context_note); recompute possible/earned from the file's OWN keyword
   list; `raw == round(earned/possible*100)` (Python banker's rounding);
   rating band (Excellent >80 / Good 60-79 / Needs Work <60); if "25%" in
   `penalty_applied` then penalized == `int(raw*0.75)` else penalized == raw;
   `seniority_penalty_applied` flag present.
   (b) `resume_match.md` — `## Overall Match Score: N% raw / M%` two-number header
   (or single-number form) must match the JSON raw/penalized.
   (c) run `generate_resume.py` via subprocess with `cwd=app_dir`; `tailored_resume.docx`
   exists and >30KB; python-docx readback text >1000 chars.
   (d) forbidden-claim grep over the docx text: word-boundary regexes + `re.I`,
   expect ZERO hits.
   (e) stale-number grep across the app dir — skip for fresh builds (nothing to check).
3. Print PASS/FAIL per check; print a final "ALL CHECKS PASSED" line; exit nonzero
   on any fail.
4. `os.unlink(path)` after the run; the single tool result now carries the full
   passing evidence line.

## String-templating trap (bit TWICE this session)
When generating a Python verifier/script FROM a Python template string, never use
the `%` operator on the template: the embedded script's own `%` characters
(regex `r"(\d+)%"`, the literal `"25%"`, `r"8\+?\s*years"`) make `%`-formatting
raise `TypeError: not enough arguments for format string` even when you supplied
exactly one `%s` — Python sees every stray `%x` as a conversion specifier.
Remedies (any works): embed the script as a plain literal with the path hardcoded
(no substitution at all), use `.replace()` / `.format()`, or `write_file`
directly to the temp path. General rule for ANY "generate a script from a
template" pattern: prefer literal embedding over `%`-formatting.
Alternative host: a single bash heredoc (`python - <<'EOF'`) via the terminal
tool also works on git-bash for one-shot temp scripts.

## More suite defects found in the app_21 build (2026-08-17)

1. **`--forbidden` is split on `|` — alternation groups/parens crash it.** The
   verifier does `args.forbidden.split("|")` then compiles each segment as its own
   pattern. A single segment containing a group like `ml\s*(infrastructure|infra|platform)`
   becomes `...|infra|platform)` → `re.error: missing ), unterminated subpattern`.
   Pass only FLAT patterns (no inner `|`, no parens): spell each alternative out
   (`\bml\s*infra\b|\bml\s*platform\b|\bml\s*infrastructure\b`). Complex alternations
   belong in the generator's embedded grep (a Python list — no string split there,
   so groups are fine). Hit twice in one session before the flat rewrite.
2. **The "fixed" on-disk variant can print FAILs yet exit 0.** Once `check()` gains
   `fails=None` (upstream's mid-session fix), call sites still pass only 2 args →
   `fails` stays None → failures are PRINTED but never appended → the final summary
   always says "ALL CHECKS PASSED" and the exit code is 0 even when individual
   checks failed. NEVER trust the suite's summary line or exit code alone: read the
   per-line PASS/FAIL output AND run an independent recompute (JSON math from the
   file's own keyword list) + an independent docx grep (same word-boundary patterns).
   The suite is a convenience, not a verdict.
3. **Before blaming the artifact, diff your check pattern against the artifact's
   exact text.** A Gate-1 check failed once because the check demanded
   `stretch floor (50%)` (space) while the artifact correctly says `stretch.floor (50%)`
   (period, as precedent uses). A failed check showing the EXPECTED content present
   in the file = pattern bug in the checker, not an artifact defect.
4. **Only the DOCX is hard-forbidden-clean.** `cover_letter.txt`, `application_qa.md`,
   `resume_match.md`, and the logs legitimately contain gap-domain terms as honest
   denials ("I haven't owned an observability product"), eligibility flags, and
   audit trails. Hard-require zero hits on `tailored_resume.docx` only; treat matches
   in other files as informational. Sweeping every file with `--forbidden` would flag
   the package for its own honesty.
5. **`tailored_resume.docx` is a generated artifact — its hash changes every run.**
   Re-verifying regenerates it (and must: the verifier re-runs `generate_resume.py`).
   Don't compare docx hashes across runs; verify the freshly regenerated docx.

## Precedent note (app_22 — third no-penalty PM build)
app_22 (Guidewire "Outbound Product Manager, AI and Workflow Automation"):
plain Product Manager title, no Senior/Lead/Principal qualifier, and the JD's
"8+ years" sitting in **Preferred** does NOT trigger the app_17 substance-
exception (that fires on a hard REQUIRED year-gate + executive-presenting +
large-product-area ownership — check those three signals, not the mere presence
of a year figure). 23/34 = 68% raw = 68% penalized, Gate 1 PASSED (>65),
Gate 2 PASSED (comp $138-245k far above the $36k floor). When the JD's core
subject-matter (agentic AI, workflow automation, AI-first mindset) is the
candidate's genuine hands-on strength, a 60s raw score is honest and stageable —
the domain gaps (here: P&C insurance, BPMN/DMN, MCP, AWS/cloud, serverless,
8+ years) stay `found_in_resume:false` and keep the forbidden grep busy.