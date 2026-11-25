# Question Bank Shortlist — 2026-11-17

This 37-question core was promoted first on 2026-11-17, then superseded by
the 160-question merged candidate now live in `shared/question_bank.yaml`.
Backups: `shared/question_bank.yaml.10-seed.bak` and
`shared/question_bank.yaml.37.bak`.

## What this is

- 37 curated questions: the 10 seeds plus 27 merged from the 1,333-row crawl.
- This is below the 100 ceiling on purpose. Most crawled rows were
  duplicates, consent/privacy fields, early-career fields, or role-specific
  sales and healthcare screens that do not belong in a general bank.
- Every grouped row keeps `merged_from` and `variants_seen`, so no raw
  wording is lost.
- `source_count` is the sum of the raw rows behind the group.
- `qb_161` restores the job-title question that the employer cluster
  swallowed; its true count is unknown.

## Counts

| Role | Count |
|---|---|
| star | 11 |
| experience | 7 |
| profile | 19 |

| Category | Count |
|---|---|
| behavioral | 10 |
| motivation | 1 |
| experience_screen | 6 |
| technical | 1 |
| work_authorization | 3 |
| compensation | 1 |
| logistics | 5 |
| factual_profile | 6 |
| legal_screen | 3 |
| language | 1 |

## The questions

### star

| id | category | question | raw rows | merged from |
|---|---|---|---|---|
| qb_001 | behavioral | Tell me about a time you had to influence a stakeholder who didn't report to you. | 1 | qb_001 |
| qb_002 | behavioral | Describe a time when you had to make a product decision with incomplete information. | 1 | qb_002 |
| qb_003 | behavioral | How do you prioritize features when you can't build them all? | 1 | qb_003 |
| qb_004 | behavioral | Give me an example of a time you shipped a product under a tight deadline. | 1 | qb_004 |
| qb_005 | behavioral | Tell me about a time you received critical feedback and how you acted on it. | 1 | qb_005 |
| qb_006 | behavioral | Describe a situation where you had to work with a team that was resistant to change. | 1 | qb_006 |
| qb_007 | behavioral | What's the most difficult tradeoff you've had to make in product management? | 1 | qb_007 |
| qb_008 | behavioral | How do you measure the success of a product feature? | 1 | qb_008 |
| qb_009 | behavioral | Tell me about a product you built that failed. What did you learn? | 1 | qb_009 |
| qb_010 | behavioral | How do you approach understanding user needs when entering a new domain? | 1 | qb_010 |
| qb_013 | motivation | Why do you want to work here? | 32 | qb_013, qb_038, qb_088, qb_113, qb_134 |

### experience

| id | category | question | raw rows | merged from |
|---|---|---|---|---|
| qb_019 | experience_screen | How many years of relevant experience do you have? | 6 | qb_019, qb_156 |
| qb_127 | experience_screen | Please indicate what you have experience with. | 2 | qb_127 |
| qb_128 | experience_screen | Is there any other relevant experience or project you would like us to know about? | 1 | qb_128 |
| qb_068 | experience_screen | Do you have experience in DevOps? | 22 | qb_068 |
| qb_078 | experience_screen | Which scripting or programming languages do you have experience with? | 4 | qb_078 |
| qb_115 | technical | Have you completed coding assessments involving data structures and algorithms? | 1 | qb_115 |
| qb_121 | experience_screen | Are you currently in a manager-level role, or have you held a Manager or Staff-equivalent position? | 1 | qb_121 |

### profile

| id | category | question | raw rows | merged from |
|---|---|---|---|---|
| qb_018 | work_authorization | Will you now or in the future require sponsorship for an employment visa? | 130 | qb_018, qb_020, qb_041, qb_063, qb_075, qb_079, qb_123, qb_141 |
| qb_017 | work_authorization | Are you legally authorized to work in the country where this job is located? | 169 | qb_017, qb_028, qb_044, qb_054, qb_064, qb_074, qb_096, qb_122 |
| qb_046 | work_authorization | Which work authorization best describes you? | 4 | qb_046 |
| qb_104 | compensation | What are your salary expectations? | 7 | qb_104, qb_105, qb_125, qb_149, qb_160 |
| qb_027 | logistics | Where are you currently located? | 77 | qb_027, qb_033, qb_034, qb_053, qb_080, qb_109, qb_158 |
| qb_014 | logistics | Where do you intend to work from? | 40 | qb_014, qb_032, qb_065, qb_098 |
| qb_045 | logistics | Are you willing to work from the office or relocate? | 65 | qb_045, qb_059, qb_086, qb_108, qb_124, qb_126, qb_130, qb_142, qb_146, qb_148, qb_152, qb_153, qb_154, qb_159 |
| qb_025 | logistics | When can you start? | 9 | qb_025, qb_067 |
| qb_119 | logistics | How many years have you worked remotely? | 1 | qb_119 |
| qb_011 | factual_profile | How did you hear about us? | 125 | qb_011, qb_039, qb_052, qb_155 |
| qb_012 | factual_profile | Who is your current or previous employer? | 50 | qb_012 |
| qb_057 | factual_profile | What is your preferred name? | 22 | qb_057 |
| qb_043 | factual_profile | Please share a link to your portfolio or examples of your work. | 24 | qb_043 |
| qb_040 | factual_profile | If you heard about us through a referral, please state the employee's name. | 28 | qb_040, qb_100 |
| qb_021 | legal_screen | Are you currently subject to any non-compete or non-solicitation agreement? | 22 | qb_021 |
| qb_103 | legal_screen | Do you have any immediate relatives working at this company? | 1 | qb_103 |
| qb_099 | legal_screen | Are you currently in process with other companies? | 1 | qb_099 |
| qb_031 | language | What languages do you speak and how proficient are you? | 50 | qb_031, qb_107 |
| qb_161 | factual_profile | What is your current or previous job title? | 0 | - |

## Review notes

1. The 10 seeds keep their STAR mapping; their answers are still
   `PLACEHOLDER`.
2. The motivation group collapses five company-specific variants into
   one question; use the company research cache to answer it.
3. The profile groups pull from `target-profile.yaml` and `USER.md`, not
   from a STAR story.
4. The work-authorization answers are country-dependent. Read
   `jurisdiction_dependent` before answering.
5. If a role asks a role-specific screen (sales, healthcare, locum),
   answer it from the JD and the resume, not from this general bank.
