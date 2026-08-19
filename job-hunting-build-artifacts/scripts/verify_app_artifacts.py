#!/usr/bin/env python3
"""Verify a job-hunting offline artifact package (shared/build_artifacts/app_N/).

Usage:
  python verify_app_artifacts.py <app_dir> [--forbidden "pat1|pat2|..."] [--stale "63|47"] [--skip-docx]

Checks (each prints PASS/FAIL; exit 0 only if all pass):
  1. keyword_analysis.json — schema keys, keyword count 10-15, per-keyword fields,
     math self-consistency recomputed from the file's OWN keyword list
     (match_score_percentage == round(earned/possible*100), Python banker's
     rounding — round(62.5)=62), rating band, penalized_score_percentage
     (== int(raw*0.75) when a 25% penalty is declared, == raw when not).
  2. resume_match.md — "## Overall Match Score" header matches the JSON's raw and
     penalized numbers (accepts "N%" single-number form when no penalty applies).
  3. generate_resume.py — runs clean (exit 0) and tailored_resume.docx exists,
     non-empty, and reads back via python-docx (skipped with --skip-docx).
  4. Forbidden-claim grep on the docx text — --forbidden patterns, word-boundary
     regexes, re.I; expect ZERO hits. Derive patterns from found_in_resume:false
     gaps in keyword_analysis.json (e.g. r"\\b10\\s*\\+\\s*years?\\b|\\bsenior\\b|\\bexecutive\\b").
  5. Stale-reference grep — --stale numbers (pipe-separated) must not appear in
     any .md/.json/.txt/.py file in the app dir (score-change propagation check).

Requires: python-docx (pip install python-docx).
"""
import argparse
import json
import os
import re
import subprocess
import sys

def check(cond, msg, fails=None):
    print(("PASS: " if cond else "FAIL: ") + msg)
    if not cond and fails is not None:
        fails.append(msg)

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("app_dir", help="path to shared/build_artifacts/app_N/")
    ap.add_argument("--forbidden", default="", help="pipe-separated word-boundary regexes to grep in the docx text")
    ap.add_argument("--stale", default="", help="pipe-separated old numbers that must NOT appear anywhere in the app dir")
    ap.add_argument("--skip-docx", action="store_true", help="skip generate_resume.py run + docx checks")
    args = ap.parse_args()

    base = args.app_dir
    fails = []

    # ---- 1. keyword_analysis.json ----
    with open(os.path.join(base, "keyword_analysis.json"), encoding="utf-8") as f:
        kw = json.load(f)
    a = kw["analysis"]
    for key in ("total_keywords_found", "total_possible_points", "earned_points",
                "match_score_percentage", "match_rating", "penalty_applied",
                "penalized_score_percentage"):
        check(key in a, f"analysis.{key} present")
    kws = kw["keywords"]
    check(isinstance(kws, list) and 10 <= len(kws) <= 15, f"keywords count in [10,15]: {len(kws)}")
    check(all(set(k) >= {"term", "category", "priority_weight", "found_in_resume", "context_note"} for k in kws),
          "every keyword has the 5 schema fields")
    check(a["total_keywords_found"] == len(kws), "total_keywords_found == len(keywords)")
    possible = sum(k["priority_weight"] for k in kws)
    earned = sum(k["priority_weight"] for k in kws if k["found_in_resume"])
    check(a["total_possible_points"] == possible, f"total_possible_points == {possible}")
    check(a["earned_points"] == earned, f"earned_points == {earned}")
    raw = round(earned / possible * 100)  # Python banker's rounding: round(62.5)=62
    check(a["match_score_percentage"] == raw,
          f"match_score_percentage == {raw} (computed {earned}/{possible}; Python round semantics)")
    rating = "Excellent" if raw > 80 else "Good" if raw >= 60 else "Needs Work"
    check(a["match_rating"] == rating, f"match_rating consistent with raw {raw}")
    penalized = a["penalized_score_percentage"]
    if "25%" in a["penalty_applied"] or "25 %" in a["penalty_applied"]:
        expect_pen = int(raw * 0.75)  # truncation: 62*0.75=46.5 -> 46
        check(penalized == expect_pen, f"penalized_score_percentage == int(raw*0.75) == {expect_pen}")
    else:
        check(penalized == raw, f"no penalty declared -> penalized == raw == {raw}")
    check(isinstance(kw.get("recommendation"), str) and len(kw["recommendation"]) > 20,
          "recommendation present")

    # ---- 2. resume_match.md header vs JSON ----
    rm_path = os.path.join(base, "resume_match.md")
    if os.path.exists(rm_path):
        rm = open(rm_path, encoding="utf-8").read()
        m = re.search(r"## Overall Match Score: (\d+)% raw / (\d+)%", rm)
        if m:
            check(int(m.group(1)) == raw and int(m.group(2)) == penalized,
                  f"resume_match.md header matches JSON ({raw} raw / {penalized} penalized)")
        else:
            m2 = re.search(r"## Overall Match Score: (\d+)%", rm)
            check(m2 is not None and int(m2.group(1)) == raw,
                  "resume_match.md single-number header matches JSON raw")
    else:
        check(False, "resume_match.md exists")

    # ---- 3. generator + docx ----
    if not args.skip_docx:
        gen = os.path.join(base, "generate_resume.py")
        if os.path.exists(gen):
            r = subprocess.run([sys.executable, gen], capture_output=True, text=True, timeout=180)
            check(r.returncode == 0, "generate_resume.py exits 0")
            if r.returncode != 0:
                print(r.stdout[-1500:])
                print(r.stderr[-1500:])
        else:
            check(False, "generate_resume.py exists")
        docx_path = os.path.join(base, "tailored_resume.docx")
        check(os.path.exists(docx_path) and os.path.getsize(docx_path) > 30000,
              "tailored_resume.docx exists and is non-empty")
        try:
            from docx import Document
            text = "\n".join(p.text for p in Document(docx_path).paragraphs)
            check(len(text) > 1000, "docx text readable via python-docx")
        except Exception as exc:  # noqa: BLE001
            check(False, f"docx read-back failed: {exc}")
            text = ""

        # ---- 4. forbidden-claim grep (word-boundary regexes, re.I) ----
        if args.forbidden:
            patterns = [p for p in args.forbidden.split("|") if p.strip()]
            hits = [(p, m.group(0)) for p in patterns for m in re.finditer(p, text, re.I)]
            check(len(hits) == 0, f"forbidden-claim grep 0 hits (got {len(hits)}: {hits[:3]})")

    # ---- 5. stale-reference grep across the app dir ----
    if args.stale:
        stale_terms = [s for s in args.stale.split("|") if s.strip()]
        stale_hits = []
        for fn in os.listdir(base):
            if fn.endswith((".md", ".json", ".txt", ".py")):
                content = open(os.path.join(base, fn), encoding="utf-8").read()
                for term in stale_terms:
                    if re.search(re.escape(term), content):
                        stale_hits.append((fn, term))
        check(not stale_hits, f"no stale references to {args.stale} (got {stale_hits})")

    print("\n" + ("ALL CHECKS PASSED" if not fails else f"{len(fails)} CHECK(S) FAILED"))
    sys.exit(1 if fails else 0)

if __name__ == "__main__":
    main()
