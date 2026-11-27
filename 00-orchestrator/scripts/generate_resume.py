#!/usr/bin/env python
"""
Generalized Stage 5 — Resume Customizer.
Generates a tailored, ATS-safe .docx resume for ANY application.

Usage:  python generate_resume.py --app-id <id> --title-displayed "Title" --values "Value1|Evidence1|Value2|Evidence2..."

Reads from  build_artifacts/app_{id}/keyword_analysis.json
            build_artifacts/app_{id}/resume_match.md
            shared/target-profile.yaml      (fidelity_mode)
            shared/candidate.yaml           (the candidate's career record)

Writes:     build_artifacts/app_{id}/tailored_resume.docx

The career record is DATA, not code: shared/candidate.yaml is the single
source of truth for name, contacts, summary, experience, projects,
education and skills, so a different candidate needs no change to this
script. shared/candidate.yaml.example shows the structure; the real file
is gitignored because it carries personal contact data.
"""
import json, os, sys, argparse

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SHARED = os.path.join(BASE, "shared")
CANDIDATE_PATH = os.path.join(SHARED, "candidate.yaml")
CANDIDATE_EXAMPLE = os.path.join(SHARED, "candidate.yaml.example")


def load_candidate():
    """Load shared/candidate.yaml, or fail loudly with the fix.

    A missing career record is a configuration error, not a reason to
    fall back to a hardcoded one: the hardcoded copy is exactly the
    coupling this script exists to remove (and it is where retracted
    claims used to hide).
    """
    import yaml

    path = CANDIDATE_PATH
    if not os.path.exists(path):
        path = CANDIDATE_EXAMPLE
        print(
            "WARNING: shared/candidate.yaml not found — using "
            "candidate.yaml.example (placeholder data). Copy the example to "
            "candidate.yaml and fill it in.",
            file=sys.stderr,
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or not data.get("identity", {}).get("name"):
        raise SystemExit(
            "ERROR: shared/candidate.yaml has no identity.name — copy "
            "candidate.yaml.example and fill it in."
        )
    return data


def build_resume_docx(app_id, title_displayed, values_aligned, company_name, role_title):
    """Generate tailored .docx for the given app."""
    from docx import Document
    from docx.shared import Pt

    cand = load_candidate()
    ident = cand["identity"]
    contacts = ident.get("contacts", {})
    headline = title_displayed or ident.get("headline_default", "")

    artifacts_dir = os.path.join(SHARED, "build_artifacts", f"app_{app_id}")
    kw_path = os.path.join(artifacts_dir, "keyword_analysis.json")
    rm_path = os.path.join(artifacts_dir, "resume_match.md")
    output_path = os.path.join(artifacts_dir, "tailored_resume.docx")

    # Load keyword analysis for skill emphasis
    with open(kw_path) as f:
        kw = json.load(f)

    # Load resume match for context
    with open(rm_path, encoding="utf-8") as f:
        rm_text = f.read()

    # Load target profile for fidelity context
    try:
        import yaml
        with open(os.path.join(SHARED, "target-profile.yaml")) as f:
            tp = yaml.safe_load(f)
    except Exception:
        tp = {"fidelity_mode": "strict"}

    # ---- Create document ----
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(10)
    style.paragraph_format.space_after = Pt(4)
    style.paragraph_format.line_spacing = 1.05

    # ---- Header ----
    p = doc.add_paragraph()
    run = p.add_run(ident["name"])
    run.bold = True
    run.font.size = Pt(16)
    contact_line = " | ".join(
        v for v in [
            headline,
            contacts.get("city", ""),
            contacts.get("email", ""),
            contacts.get("phone", ""),
            contacts.get("github", ""),
            contacts.get("website", ""),
        ] if v
    )
    p.add_run("\n" + contact_line).font.size = Pt(9)

    # ---- Professional Summary ----
    doc.add_heading("PROFESSIONAL SUMMARY", level=0).runs[0].font.size = Pt(8)
    p = doc.add_paragraph(cand.get("summary", ""))
    for run in p.runs:
        run.font.size = Pt(9)

    # ---- Professional Experience ----
    doc.add_heading("PROFESSIONAL EXPERIENCE", level=0).runs[0].font.size = Pt(8)
    for role in cand.get("experience", []):
        doc.add_paragraph(
            f"{role.get('title', '')} | {role.get('company', '')} ({role.get('industry', '')})",
            style='List Bullet')
        doc.add_paragraph(
            f"{role.get('dates', '')} | {role.get('location', '')}", style='List Bullet')
        for bullet in role.get("bullets", []):
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(bullet)

    # ---- Professional Projects ----
    projects = cand.get("projects", [])
    if projects:
        doc.add_heading("PROFESSIONAL PROJECTS", level=0).runs[0].font.size = Pt(8)
        for proj in projects:
            doc.add_paragraph(proj.get("name", ""), style='List Bullet')
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(proj.get("blurb", ""))
            if proj.get("evidence"):
                p = doc.add_paragraph(style='List Bullet')
                p.add_run(f"Evidence: {proj['evidence']}")

    # ---- Education ----
    doc.add_heading("EDUCATION", level=0).runs[0].font.size = Pt(8)
    for line in cand.get("education", []):
        p = doc.add_paragraph(style='List Bullet')
        p.add_run(line)

    # ---- Skills ----
    doc.add_heading("SKILLS", level=0).runs[0].font.size = Pt(8)

    base_skills = list(cand.get("skills", []))
    skills = base_skills
    if kw and "keywords" in kw:
        critical_terms = [k["term"] for k in kw["keywords"]
                         if k.get("category") in ("A", "B") and k.get("priority_weight", 0) >= 2
                         and k.get("found_in_resume", False)]
        # Move critical terms to front while maintaining uniqueness
        ordered = []
        for t in critical_terms:
            if t in base_skills and t not in ordered:
                ordered.append(t)
        for s in base_skills:
            if s not in ordered:
                ordered.append(s)
        skills = ordered

    # Build skills paragraph
    p = doc.add_paragraph()
    for i, skill in enumerate(skills):
        if i > 0:
            p.add_run(" | ")
        p.add_run(skill)
    for run in p.runs:
        run.font.size = Pt(9)

    # ---- Values Alignment (if company values provided) ----
    if values_aligned:
        doc.add_heading("VALUES ALIGNMENT", level=0).runs[0].font.size = Pt(8)
        for val_name, evidence in values_aligned:
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(f"**{val_name}**:")
            p = doc.add_paragraph(style='List Bullet')
            p.add_run(evidence)

    # ---- Save ----
    doc.save(output_path)
    print(f"Resume saved to: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-id", type=int, required=True)
    parser.add_argument("--title-displayed", default=None,
                        help="Overrides the resume headline for this application")
    parser.add_argument("--values", default="",
                        help="Pipe-separated: 'Value1|Evidence1|Value2|Evidence2'")
    parser.add_argument("--company", default="")
    parser.add_argument("--role", default="")
    args = parser.parse_args()

    # Parse values alignment
    values_aligned = []
    if args.values:
        parts = args.values.split("|")
        for i in range(0, len(parts) - 1, 2):
            if parts[i].strip() and parts[i+1].strip():
                values_aligned.append((parts[i].strip(), parts[i+1].strip()))

    if args.title_displayed is None:
        # Default headline comes from the candidate record, not a hardcoded
        # job title.
        args.title_displayed = ""

    build_resume_docx(
        app_id=args.app_id,
        title_displayed=args.title_displayed,
        values_aligned=values_aligned,
        company_name=args.company,
        role_title=args.role,
    )


if __name__ == "__main__":
    main()