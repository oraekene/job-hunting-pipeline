# Question Bank Review — 2026-11-17

This review led to the 160-question promotion on 2026-11-17. The live bank is
now `shared/question_bank.yaml`; the 37-question core was promoted first and
is kept as a subset.

## Summary

- 160 questions: 10 live seeds plus 150 crawled canonical questions.
- Source corpus: 1,333 raw rows from 8 companies (Stripe, Doximity, Brex,
  Airbnb, Coursera, Datadog, Flexport, Figma).
- Clustering: 163 distinct questions before the top-150 cut.
- Bank roles: 16 STAR, 26 experience, 89 profile, 29 form-only, 0 need a manual category.
- Categories are a first-pass heuristic. Change any row.
- `variant_dimensions` is empty everywhere; the human pass sets it only
  where context genuinely changes the answer.

## Counts by category

| Category | Role | Count |
|---|---|---|
| behavioral | star | 11 |
| motivation | star | 5 |
| experience_screen | experience | 25 |
| technical | experience | 1 |
| work_authorization | profile | 18 |
| compensation | profile | 5 |
| logistics | profile | 31 |
| factual_profile | profile | 18 |
| legal_screen | profile | 5 |
| language | profile | 12 |
| consent | form_only | 15 |
| demographic | form_only | 3 |
| early_career | form_only | 11 |

## How to read the four roles

- **STAR**: answered from a story in `memory/star-story-bank.md`.
- **Experience**: a yes/no screen that needs evidence from the resume or
  domain knowledge, not a full story.
- **Profile**: answered from `target-profile.yaml`, `USER.md` or the
  facts in the bank. No story needed.
- **Form-only**: consent, privacy, demographic and early-career fields.
  Do not answer these from a STAR story. Most should not enter the
  reviewed interview bank at all.
- **Review**: the classifier could not place it. Decide by hand.

## STAR questions (16)

| id | category | question | src | jurisdiction | origin |
|---|---|---|---|---|---|
| qb_001 | behavioral (stakeholder_management) | Tell me about a time you had to influence a stakeholder who didn't report to you. | 1 | no | live_seed |
| qb_002 | behavioral (decision_making) | Describe a time when you had to make a product decision with incomplete information. | 1 | no | live_seed |
| qb_003 | behavioral (prioritization) | How do you prioritize features when you can't build them all? | 1 | no | live_seed |
| qb_004 | behavioral (execution) | Give me an example of a time you shipped a product under a tight deadline. | 1 | no | live_seed |
| qb_005 | behavioral (feedback) | Tell me about a time you received critical feedback and how you acted on it. | 1 | no | live_seed |
| qb_006 | behavioral (team_leadership) | Describe a situation where you had to work with a team that was resistant to change. | 1 | no | live_seed |
| qb_007 | behavioral (tradeoffs) | What's the most difficult tradeoff you've had to make in product management? | 1 | no | live_seed |
| qb_008 | behavioral (metrics) | How do you measure the success of a product feature? | 1 | no | live_seed |
| qb_009 | behavioral (failure_recovery) | Tell me about a product you built that failed. What did you learn? | 1 | no | live_seed |
| qb_010 | behavioral (user_research) | How do you approach understanding user needs when entering a new domain? | 1 | no | live_seed |
| qb_013 | motivation | Why do you want to join Figma? | 25 | no | crawled |
| qb_038 | motivation | Why have you chosen to apply to Airbnb? | 4 | no | crawled |
| qb_088 | motivation | Tell us why you are interested in building an applied AI career at Datadog. | 1 | no | crawled |
| qb_112 | behavioral | Describe any disaster response you managed. What was the scope (people served, number of NGO partners involved across APAC etc), and what was your role? | 1 | no | crawled |
| qb_113 | motivation | What makes you interested to work at Airbnb ? | 1 | no | crawled |
| qb_134 | motivation | Why do you want to work at Doximity? | 1 | no | crawled |

## Experience and technical screens (26)

| id | category | question | src | jurisdiction | origin |
|---|---|---|---|---|---|
| qb_019 | experience_screen | How many years of experience do you have? | 5 | no | crawled |
| qb_067 | experience_screen | Do you have experience in DevOps? | 4 | no | crawled |
| qb_087 | experience_screen | Which scripting / programming languages do you have experience with? | 1 | no | crawled |
| qb_089 | experience_screen | Do you have experience supporting a sales team? | 3 | no | crawled |
| qb_100 | experience_screen | Do you have experience working with Prescription (Rx) and Medical Claims (Dx) data? | 3 | no | crawled |
| qb_101 | experience_screen | How many years of experience do you have in air freight operations? | 2 | no | crawled |
| qb_105 | experience_screen | List the countries and disaster types you have worked on in emergency response (for example, floods, earthquakes, cyclones, displacement). For each, briefly note your role. | 1 | no | crawled |
| qb_110 | experience_screen | How long have you worked in healthcare? | 1 | no | crawled |
| qb_111 | experience_screen | Do you have experience in B2B sales, business development, or sales development, including at least 1 year of hands-on outbound prospecting? | 1 | no | crawled |
| qb_114 | experience_screen | How many years of relevant experience do you have in emergency or disaster response operations (for example, humanitarian response, disaster relief programs, or emergency management)? | 1 | no | crawled |
| qb_115 | technical | Have you previously completed coding assessments involving data structures and algorithms (e.g., HackerRank/LeetCode-style questions)? | 1 | no | crawled |
| qb_121 | experience_screen | Are you currently in a manager-level role, or have you previously held a Manager or Staff-equivalent position? | 1 | no | crawled |
| qb_127 | experience_screen | Please indicate what you have experience with. | 2 | no | crawled |
| qb_128 | experience_screen | Is there any other relevant experience or project that you have worked on that you would like our team to know about? | 1 | no | crawled |
| qb_129 | experience_screen | Do you have experience in managing the end-to-end P2P, T&E, corporate cards, and month-end close? | 1 | no | crawled |
| qb_132 | experience_screen | Which sales motions have you owned | 2 | no | crawled |
| qb_133 | experience_screen | In your most recent sales role, what size companies did you primarily sell to? | 2 | no | crawled |
| qb_135 | experience_screen | Have you used tool like NetSuite, Coupa, ZIP, Navan, and Workday Expenses or similar softwares? | 1 | no | crawled |
| qb_137 | experience_screen | For enterprise deals you personally closed in the past 24 months, what were your typical annual contract value and sales-cycle length? | 2 | no | crawled |
| qb_138 | experience_screen | How many accounts do you currently manage? | 2 | no | crawled |
| qb_139 | experience_screen | How many years of experience do you have in the locum tenens staffing industry (temporary placement of MD/DO/APP/CRNA/NP/PA providers)? | 1 | no | crawled |
| qb_143 | experience_screen | Do you have 5+ years of sales experience at a technology company? | 1 | no | crawled |
| qb_144 | experience_screen | How many years of experience do you have in the locum tenens (MD/DO/APP/CRNA) staffing industry? | 1 | no | crawled |
| qb_147 | experience_screen | Do you have 3+ years of full sales cycle experience, building an outbound pipeline by self hunting and prospecting net new logos through close and implementation? | 1 | no | crawled |
| qb_156 | experience_screen | What is your total years of work experience? | 1 | no | crawled |
| qb_157 | experience_screen | Which markets do you have experience selling into? | 1 | no | crawled |

## Profile and target-profile fields (89)

| id | category | question | src | jurisdiction | origin |
|---|---|---|---|---|---|
| qb_011 | factual_profile | How did you hear about us? | 81 | no | crawled |
| qb_012 | factual_profile | Who is your current or previous employer? | 50 | no | crawled |
| qb_014 | logistics | From where do you intend to work? | 25 | no | crawled |
| qb_015 | work_authorization | Are you authorized to work in the country for which you applied? | 25 | no | crawled |
| qb_016 | factual_profile | Have you ever worked for Figma before, as an employee or a contractor/consultant? | 25 | no | crawled |
| qb_017 | work_authorization | Are you legally entitled to work in Canada? | 58 | yes | crawled |
| qb_018 | work_authorization | Will you now or in the future require sponsorship of an employment visa? | 22 | yes | crawled |
| qb_020 | work_authorization | Will you now or in the future require company sponsorship to retain or extend your work authorization in the country where the job is located? | 23 | yes | crawled |
| qb_021 | legal_screen | Are you currently subject to any non-compete or non-solicitation agreement that would impact your ability to work at Airbnb or prevent you from accepting a job offer from Airbnb? | 22 | no | crawled |
| qb_022 | factual_profile | Are you currently or have you ever worked for Airbnb in any capacity? This could include, but is not limited to, a full-time employee, intern, apprentice, or contingent worker. | 22 | no | crawled |
| qb_024 | factual_profile | Have you previously been employed by Flexport or any of its entities; or by an agency representing Flexport? | 20 | no | crawled |
| qb_025 | logistics | When are you available to start with Flexport? | 5 | no | crawled |
| qb_026 | legal_screen | If you currently work, or have previously worked, at Capital One or a company acquired by Capital One, please provide your Employee ID (EID). This information is required for former/current employees. | 34 | no | crawled |
| qb_027 | logistics | Please select the country where you currently reside. | 25 | no | crawled |
| qb_028 | language | Are you fluent in German? | 4 | no | crawled |
| qb_029 | factual_profile | Please share a link to your portfolio or examples of your work. | 1 | no | crawled |
| qb_032 | logistics | What location are you planning to work from? | 13 | no | crawled |
| qb_033 | logistics | Are you currently residing in the US? | 22 | no | crawled |
| qb_034 | logistics | Are you based in Japan? | 4 | no | crawled |
| qb_039 | factual_profile | How did you first hear about Flexport? | 18 | no | crawled |
| qb_040 | factual_profile | If you heard about us through a referral, please state the Brex employee's name. | 25 | no | crawled |
| qb_041 | work_authorization | Will you require Stripe to sponsor you for a work permit now or in the future to work in Singapore? | 24 | yes | crawled |
| qb_042 | logistics | In what cities are you available to work? | 24 | no | crawled |
| qb_043 | language | Please select all the languages you speak fluently. | 24 | no | crawled |
| qb_044 | work_authorization | Which work authorization best describes you? | 12 | yes | crawled |
| qb_045 | factual_profile | Have you ever been employed by Coursera or Udemy? | 22 | no | crawled |
| qb_046 | logistics | Are you a Singapore Citizen or Permanent Resident? | 4 | no | crawled |
| qb_049 | language | What is your fluency in French? | 2 | no | crawled |
| qb_051 | factual_profile | Let us know which specific channel/event/medium/etc you heard about us: | 14 | no | crawled |
| qb_052 | logistics | What country are you based in? | 25 | no | crawled |
| qb_053 | work_authorization | Are you authorized to work in the location(s) you selected in your previous response? | 23 | no | crawled |
| qb_054 | work_authorization | Are you legally authorised to work full-time in the country where this job is based? | 23 | no | crawled |
| qb_056 | factual_profile | What is your preferred name? | 5 | no | crawled |
| qb_057 | legal_screen | COURSERA IS A U.S. GOVERNMENT CONTRACTOR AND WE ARE REQUIRED TO INQUIRE ABOUT CONFLICTS BEFORE WE CAN RECRUIT CURRENT OR FORMER GOVERNMENT EMPLOYEES. IF THIS APPLIES TO YOU, WE REQUEST A LETTER FROM YOUR SUPERVISOR THAT THEY HAVE BEEN INFORMED ABOUT YOUR CONTACT WITH COURSERA (OR AS A FORMER EMPLOYEE, A LETTER STATING AN ETHICS OPINION WHICH IDENTIFIES ANY LIMITATIONS WHICH APPLY TO YOUR WORK IN THE PRIVATE SECTOR). THE LETTER SHOULD IDENTIFY ANY CONFLICTS OR POTENTIAL CONFLICTS, IF ANY EXIST. | 22 | no | crawled |
| qb_058 | logistics | What city are you based? Are you willing to come to the office 2 x a week in Barcelona at your own cost? | 1 | no | crawled |
| qb_059 | language | Are you fluent in both Spanish & English (oral and written)? | 1 | no | crawled |
| qb_062 | work_authorization | Will you now or in the future require Flexport to commence ("sponsor") an immigration case in order to employ you (for example, H-1B or other employment-based immigration case)? This is sometimes called "sponsorship" for an employment-based visa status. | 8 | yes | crawled |
| qb_063 | work_authorization | Are you authorized to work in the stated location of this role? | 25 | no | crawled |
| qb_064 | logistics | Please select the country or countries you anticipate working in for the role in which you are applying. | 21 | no | crawled |
| qb_070 | language | This role requires advanced fluency in English and Japanese language, both spoken and written. Please select your level of proficiency for both language. | 1 | no | crawled |
| qb_071 | work_authorization | Are you classified by the Singaporean Government as a: | 1 | no | crawled |
| qb_073 | work_authorization | Are you authorized to work lawfully in Mexico for Flexport? | 8 | no | crawled |
| qb_074 | work_authorization | If you're not authorized to work at the stated location, what sponsorship would you require for the role? | 25 | yes | crawled |
| qb_075 | factual_profile | Have you ever been employed by Stripe or a Stripe affiliate? | 21 | no | crawled |
| qb_076 | logistics | If you were offered full-time employment with Datadog, when would you be able to start? | 1 | no | crawled |
| qb_078 | work_authorization | Do you require a visa sponsorship to work in the UK? | 4 | yes | crawled |
| qb_079 | logistics | What city and state do you reside in? | 13 | no | crawled |
| qb_080 | factual_profile | Por favor indique su número CURP - Clave Única de Registro de Población (Please note your CURP number) - México | 1 | no | crawled |
| qb_085 | logistics | Do you currently live in, or plan to relocate to, the specified location to meet this in-office requirement? | 25 | no | crawled |
| qb_092 | factual_profile | Portfolio Password, if applicable | 1 | no | crawled |
| qb_094 | factual_profile | Have you been employed by Airbnb/Airbnb Global Capability Center/Airseva (previously)? | 1 | no | crawled |
| qb_095 | work_authorization | Are you eligible to work in France? | 4 | yes | crawled |
| qb_097 | logistics | If this role offers the option to work from a remote location, do you plan to work remotely? | 13 | no | crawled |
| qb_099 | legal_screen | Are you currently in process with other companies that would require us to be time sensitive? | 1 | no | crawled |
| qb_102 | legal_screen | Do you have any immediate blood relatives (parents/siblings/spouse/offspring) working or under consideration for employment at Airbnb? | 1 | no | crawled |
| qb_103 | compensation | We have posted the compensation range for this role. Please let us know if it aligns with your expectations. | 1 | no | crawled |
| qb_104 | compensation | What is your current fixed pay , bonus / variable pay and stocks (if applicable) ? | 1 | no | crawled |
| qb_106 | language | What languages do you speak and how proficient are you? | 4 | no | crawled |
| qb_107 | logistics | This role requires in-office work three days per week (Mon, Wed, Thurs). Do you acknowledge and agree to this requirement? | 25 | no | crawled |
| qb_108 | logistics | If located in the US, in what city and state do you reside? | 11 | no | crawled |
| qb_109 | factual_profile | If you selected Datadog employee in the question above, please add their name below. | 1 | no | crawled |
| qb_116 | language | What level are your German language skills? | 3 | no | crawled |
| qb_117 | factual_profile | Do you currently, or have you previously, worked at Capital One or a company acquired by Capital One as an employee, contractor, consultant, or temp? (For example Capital One Bank, N.A., Capital One Services, Inc., Chevy Chase Bank, Discover, Hibernia, ING Direct, North Fork Bank) | 25 | no | crawled |
| qb_119 | logistics | Number of years working remotely? | 1 | no | crawled |
| qb_120 | logistics | This role is based in Singapore and focuses primarily on Australia and New Zealand. Have you sold or prospected into these markets before | 1 | no | crawled |
| qb_122 | work_authorization | Êtes-vous légalement autorisé à travailler dans le pays où se situe le poste ? | 1 | no | crawled |
| qb_123 | work_authorization | Aurez-vous besoin, maintenant ou à l’avenir, du parrainage d’une entreprise pour conserver ou prolonger votre autorisation de travail dans le pays où se situe le poste ? | 1 | no | crawled |
| qb_124 | logistics | Le poste exige une disponibilité du dimanche au jeudi OU du mardi au samedi, entre 6 h et 21 h, heure locale. Avez-vous des restrictions ou des conflits d'horaire par rapport à cet horaire de travail? | 1 | no | crawled |
| qb_125 | compensation | What is your current monthly salary (THB )? | 3 | no | crawled |
| qb_126 | logistics | This role requires you to be in the Chicago office at least 50% of the month. Is this something you can commit to? | 3 | no | crawled |
| qb_130 | logistics | Si vous avez répondu « oui » à la question précédente, veuillez fournir des précisions sur vos restrictions d'horaire. | 1 | no | crawled |
| qb_131 | language | What is your Dutch language level proficiency? | 2 | no | crawled |
| qb_136 | language | Is your Italian language at native or fluent level of proficiency? | 1 | no | crawled |
| qb_140 | language | Are you fluent in Arabic and comfortable conducting sales calls and business conversations entirely in Arabic? | 1 | no | crawled |
| qb_141 | work_authorization | Do you require visa sponsorship in order to legally work in Italy? | 1 | yes | crawled |
| qb_142 | logistics | Are you open to working from the South San Francisco office at least 2-3 days per week? | 1 | no | crawled |
| qb_145 | language | Do you speak Korean at a native proficiency? | 1 | no | crawled |
| qb_146 | logistics | This full-time role requires you to work in our Guadalajara office 5 days per week. Are you currently local or willing to relocate to meet this requirement? | 1 | no | crawled |
| qb_148 | logistics | This role will be on 50% hybrid work arrangement. Will you be comfortable with this arrangement? | 1 | no | crawled |
| qb_149 | compensation | What are your salary expectations? | 1 | no | crawled |
| qb_150 | logistics | Do you have experience working with GTM and RevOps teams on capacity models? | 1 | no | crawled |
| qb_151 | language | This role requires frequent interaction with Dutch-speaking clients. What is your level of proficiency in the Dutch language? | 1 | no | crawled |
| qb_152 | logistics | If you are currently based in another country, are you agreeable to relocate to Singapore? | 1 | no | crawled |
| qb_153 | logistics | This role is based in Singapore, Stripe works on a hybrid model with 50% of the month attendance in the office, are you comfortable with the work arrangement? | 1 | no | crawled |
| qb_154 | logistics | The working hours for this role are 5:30 pm to 2:30 am IST. Are you okay working these hours? | 1 | no | crawled |
| qb_155 | factual_profile | Let us know specifically how you heard about us: | 1 | no | crawled |
| qb_158 | logistics | Are you currently located in Bangalore? | 1 | no | crawled |
| qb_159 | logistics | Are you authorized to travel to the US for work purposes? | 1 | no | crawled |
| qb_160 | compensation | What is your current annual compensation? | 1 | no | crawled |

## Form-only, do not answer from STAR (29)

| id | category | question | src | jurisdiction | origin |
|---|---|---|---|---|---|
| qb_023 | consent | Candidate AI Usage Attestation: | 20 | no | crawled |
| qb_030 | consent | I certify that the information provided in this application is true and correct to the best of my knowledge. I understand that any false statements or omissions may result in disqualification from employment consideration or, if employed, in termination. | 25 | no | crawled |
| qb_031 | consent | I understand my application will be processed in accordance with Datadog’s Candidate Privacy Policy | 25 | no | crawled |
| qb_035 | consent | Airbnb Candidate Privacy Policy | 14 | no | crawled |
| qb_036 | consent | U.S. Equal Opportunity Employment Information (Completion is voluntary) | 12 | no | crawled |
| qb_037 | consent | Before submitting your application please review the note below: | 5 | no | crawled |
| qb_047 | consent | Consent to Privacy Notice (Japan) | 3 | no | crawled |
| qb_048 | consent | Aviso de Privacidad de Airbnb (Airbnb Data Privacy Notice) - Mexico | 3 | no | crawled |
| qb_050 | early_career | Are you available for a 6-month internship? | 2 | no | crawled |
| qb_055 | early_career | Please share the full name of your major/final year specialization(s) as it would appear on your diploma. | 1 | no | crawled |
| qb_060 | early_career | Select your degree level you are pursuing. | 1 | no | crawled |
| qb_061 | early_career | When are you expected to graduate? | 1 | no | crawled |
| qb_065 | early_career | Do you have any specific academic requirements for your internship? | 1 | no | crawled |
| qb_066 | early_career | Are you in your final year of study and applying for an end-of-study internship? | 1 | no | crawled |
| qb_068 | consent | Do you consent to your application information being shared between Coursera and Udemy for recruitment purposes? | 22 | no | crawled |
| qb_069 | early_career | What are the dates for your summer break? | 1 | no | crawled |
| qb_072 | demographic | Por favor identifique su origen étnico (Please identify your ethnic origin) - Mexico | 1 | no | crawled |
| qb_077 | early_career | Are you available to relocate for this internship position and full-time if you are offered a permanent contract? | 1 | no | crawled |
| qb_081 | demographic | ¿Cuenta usted con una discapacidad? (Do you have any disabilities?) - Argentina | 1 | no | crawled |
| qb_082 | demographic | O grupo étnico-racial com o qual você se identifica. Você se declara uma pessoa: (The ethnic-racial group you identify with. You declare yourself as:) - Brazil | 1 | no | crawled |
| qb_083 | early_career | Why are you interested in joining Airbnb and specifically this internship? How does your educational background and work experience align with the role? | 1 | no | crawled |
| qb_084 | consent | Application consent for Flexport | 8 | no | crawled |
| qb_086 | consent | Do you opt-in to receive WhatsApp messages from Stripe Recruiting? | 19 | no | crawled |
| qb_090 | consent | Would you like to be considered for future job opportunities? If you accept: You allow Coursera to retain and use your application data (i.e. the data that you submit in the course of your application) to consider and contact you for other job opportunities in the future. If you provide your consent, your data will be retained and used for these purposes for up to 3 years from your last application. | 13 | no | crawled |
| qb_091 | early_career | Confirm you will provide Airbnb an Internship Agreement from your university. | 1 | no | crawled |
| qb_093 | consent | Consent to Privacy Notice (Airbnb Global Capability Center Private Limited) | 1 | no | crawled |
| qb_096 | consent | Do you consent to Brex processing your personal information for the purpose of assessing your candidacy for this position in accordance with Brex’s Applicant Privacy Policy? | 25 | no | crawled |
| qb_098 | early_career | When considering an internship at Datadog, what are the most important factors to you? | 1 | no | crawled |
| qb_118 | consent | To ensure we can focus fully on our conversation, we use BrightHire to record and transcribe interviews. This helps us get to know you better without the distraction of note-taking. We also use BrightHire to help us analyze interview notes and for internal Stripe interview quality training and assurance purposes. After the recruitment process ends, recordings may be shared internally for recruiter and interviewer training to help us improve our interview processes. Please confirm if you consent to BrightHire being enabled for this interview and for your personal data to be collected and processed for the purposes mentioned above, by responding below | 7 | no | crawled |

## Needs a manual category (0)

| id | category | question | src | jurisdiction | origin |
|---|---|---|---|---|---|

## What to review first

1. The 10 seeds: the categories are now broad behavioural, with the old
   label kept as a subcategory. The answers stay placeholders.
2. Company-specific text: several crawled questions still name a company,
   office or city. Generalise or keep as a variant.
3. Bad merges: difflib can collapse unrelated questions. Split them.
4. The `review` bucket: decide whether each row is STAR, profile, or drop.
5. Cut to about 100 before promotion, mostly from STAR, experience and
   profile.

## What happened

The 37-question shortlist was promoted first, then the 160-question merged
candidate was promoted as the live bank on 2026-11-17. The remaining work is
to map the STAR questions to stories, the experience questions to evidence,
and the profile questions to `target-profile.yaml` / `USER.md`, then write the
answer variants in `memory/star-story-bank.md`.
