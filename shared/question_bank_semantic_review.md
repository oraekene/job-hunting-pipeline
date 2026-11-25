# Semantic Question Bank — 2026-11-17

Promoted to live on 2026-11-17. `shared/question_bank.yaml` now holds these
379 questions.

379 questions: 10 seeds plus 369 semantic clusters.
Inputs: 2,176 exact-unique questions, filtered to 624 generic ones
(appearing in at least two companies or at least twice), clustered at 0.60
with TF-IDF character n-grams after stripping company names.

| Role | Count |
|---|---|
| star | 24 |
| experience | 60 |
| profile | 295 |

| Category | Count |
|---|---|
| behavioral | 13 |
| motivation | 11 |
| experience_screen | 49 |
| technical | 11 |
| work_authorization | 73 |
| compensation | 17 |
| logistics | 125 |
| factual_profile | 56 |
| legal_screen | 14 |
| language | 10 |

## Top 100 by raw occurrences

| id | category | question | rows | companies |
|---|---|---|---|---|
| qb_010 | behavioral | How do you approach understanding user needs when entering a new domain? | 1 |  |
| qb_009 | behavioral | Tell me about a product you built that failed. What did you learn? | 1 |  |
| qb_008 | behavioral | How do you measure the success of a product feature? | 1 |  |
| qb_007 | behavioral | What's the most difficult tradeoff you've had to make in product management? | 1 |  |
| qb_006 | behavioral | Describe a situation where you had to work with a team that was resistant to change. | 1 |  |
| qb_005 | behavioral | Tell me about a time you received critical feedback and how you acted on it. | 1 |  |
| qb_004 | behavioral | Give me an example of a time you shipped a product under a tight deadline. | 1 |  |
| qb_003 | behavioral | How do you prioritize features when you can't build them all? | 1 |  |
| qb_002 | behavioral | Describe a time when you had to make a product decision with incomplete information. | 1 |  |
| qb_001 | behavioral | Tell me about a time you had to influence a stakeholder who didn't report to you. | 1 |  |
| qs_0001 | factual_profile | How did you hear about this job? | 995 | agoda, airbnb, anthropic, appian... |
| qs_0003 | work_authorization | Will you now or in the future require sponsorship for employment visa status? | 728 | addepar1, anthropic, arcboatcompany, courierhealth... |
| qs_0002 | work_authorization | Are you legally authorized to work in the United States? | 584 | arcboatcompany, capstoneinvestmentadvisors, compeerfinancial, courierhealth... |
| qs_0005 | work_authorization | Are you legally authorized to work in the country where the job is located? | 249 | addepar1, airbnb, appian, atoms... |
| qs_0004 | compensation | What is your desired salary? | 160 | compeerfinancial, eqtcorporation, garnerhealth, lumbermens... |
| qs_0011 | compensation | What are your salary expectations? | 160 | agoda, atoms, cssmerge, datacor... |
| qs_0007 | work_authorization | Do you now or will you in the future require immigration sponsorship by the company for continued work-authorization? | 154 | affirm, atoms, c3ascend, chime... |
| qs_0008 | logistics | Are you willing to work in the office 5-days a week? | 89 | atoms, capstoneinvestmentadvisors, cssmerge, familyoffice... |
| qs_0013 | work_authorization | Are you legally eligible to work in the U.S.? | 84 | chime, drivewealth, hyannisportresearch, thealleninstitute... |
| qs_0006 | work_authorization | Will you now or in the future require company sponsorship to retain or extend your work authorization in the country where the job is located? | 77 | airbnb, dvtrading, scaleai, togetherai |
| qs_0014 | logistics | Which state do you currently reside in? | 68 | dvtrading, garnerhealth, scaleai, stackav... |
| qs_0059 | experience_screen | Do you currently hold a US Department of Defense Security Clearance? If so, what level of clearance? | 64 | bti36021, muonspace, scaleai, stratolaunch |
| qs_0010 | factual_profile | What is your preferred name? | 63 | doximity, drweng, jumptrading, point72... |
| qs_0086 | logistics | What is your available start date? | 62 | flexport, mavensecuritiesholdingltd, muonspace, woolpert |
| qs_0061 | factual_profile | Portfolio, Video, or Website Link | 61 | idmeuniversityrecruiting, sharkninjaoperatingllc, thenewyorktimes |
| qs_0131 | work_authorization | Will you now or ever require sponsorship to work in the United States? | 58 | affirm, capstoneinvestmentadvisors, compeerfinancial, schonfeld... |
| qs_0026 | work_authorization | Are you authorized to work in the stated location of this role? | 50 | brex |
| qs_0036 | work_authorization | Will you now require immigration sponsorship by our company to attain or maintain your employment eligibility (e.g., H-1B, E-3, TN, O-1, STEM OPT, or any immigration work authorization requiring a written submission from the company to a government agency)? | 50 | doordashusa |
| qs_0042 | factual_profile | Are you now, or have you ever been employed by Fanatics, Inc. or any of its affiliates or subsidiaries? | 50 | fanaticscollectibles, thenewyorktimes |
| qs_0057 | work_authorization | What is your current visa status? | 50 | sigmacomputing, thenewyorktimes |
| qs_0060 | logistics | What country are you applying from? | 50 | thebrattlegroup, thetradedesk |
| qs_0018 | logistics | Are you open to relocation? | 49 | anthropic, scopely, thetradedesk, voloridgeinvestmentmanagement |
| qs_0021 | work_authorization | Are you authorized to work in the country for which you applied? | 49 | figma, purestorage |
| qs_0015 | logistics | Would you need to relocate to work regularly from this office? | 48 | graphcore, graphcore-early-careers |
| qs_0024 | factual_profile | If you heard about us through a referral, please state the Brex employee's name. | 48 | brex, woolpert |
| qs_0085 | factual_profile | (Required if you answered 'yes' to "Have you previously worked at The Trade Desk?") What was your TTD work email? | 47 | thetradedesk |
| qs_0090 | work_authorization | Are you authorized to work in the location(s) you selected in your previous response? | 46 | stripe |
| qs_0092 | work_authorization | Will you immediately require EQT to sponsor you for an employment visa, such as an H-1B? | 46 | eqtcorporation |
| qs_0123 | language | In which language(s) are you fluent (written) other than English? | 46 | atoms, cssmerge, point72, stripe |
| qs_0069 | factual_profile | If yes, can you please indicate the last month you worked for Tencent and/or an affiliate company. | 44 | riotgames |
| qs_0074 | language | Please select all the languages you speak fluently. | 43 | datadog, trivago |
| qs_0108 | work_authorization | Will you need a visa sponsorship? | 42 | anthropic, thetradedesk |
| qs_0009 | work_authorization | Please select your right to work status | 41 | graphcore, graphcore-early-careers, mavensecuritiesholdingltd |
| qs_0043 | legal_screen | Are you subject to any restrictive covenants (e.g., non-compete or non-solicitation agreements)? | 41 | fanaticscollectibles, gcmgrosvenor |
| qs_0080 | work_authorization | If yes, please provide your visa type and expiration date. | 41 | drweng, dvtrading |
| qs_0088 | work_authorization | Do you currently, or will you in the future, require visa sponsorship to work in the country where this position is based? | 41 | gcmgrosvenor, scopely |
| qs_0040 | work_authorization | Will you in future require visa sponsorship to maintain work authorization? | 40 | affirm, fanaticscollectibles |
| qs_0016 | logistics | Are you willing to relocate? | 38 | cloudflare, eqtcorporation, pdtpartners, woolpert... |
| qs_0019 | motivation | Why do you want to join Figma? | 38 | figma, trivago |
| qs_0072 | logistics | Please select the country where you currently reside. | 38 | paypay, stripe |
| qs_0163 | compensation | What are your total compensation expectations? | 36 | capstoneinvestmentadvisors, eqtcorporation, hyannisportresearch, voloridgeinvestmentmanagement... |
| qs_0012 | factual_profile | What is your current or previous job title? | 34 | datacor, stripe |
| qs_0117 | logistics | Are you currently residing in this country? | 34 | coursera, paypay |
| qs_0137 | legal_screen | Do you have any relatives that are currently employed by GCM Grosvenor? | 34 | gcmgrosvenor |
| qs_0110 | logistics | Please indicate your notice period in Months | 32 | capstoneinvestmentadvisors, mavensecuritiesholdingltd, n26, woolpert |
| qs_0125 | logistics | What country are you planning to work from? | 32 | doximity, xai |
| qs_0051 | logistics | What is your current location: city? | 31 | optiverprivate, scoutmotors, woolpert |
| qs_0095 | experience_screen | Are you eligible to obtain and maintain a U.S. Government Clearance (Requires U.S Citizenship)? | 30 | inversionspace, voyagertechnologiesinc |
| qs_0143 | work_authorization | Are you authorized to work in the United States without restrictions or time limitations? | 30 | lightmatter, thebrattlegroup |
| qs_0082 | logistics | Please note this opportunity is based in our Bristol, UK office. Please confirm you are happy to proceed on this basis. | 28 | graphcore, graphcore-early-careers |
| qs_0158 | logistics | This role is based out of the Scout Motors headquarters in Charlotte, North Carolina. Employees must live within 60 miles of the site for commuting. If you are not currently within that distance, relocation within 3-6 months of your start date may be required. Please select the option that best describes your current situation: | 28 | scoutmotors |
| qs_0046 | factual_profile | How did you hear about this position? If referred, who referred you? | 27 | datacor, lumbermens |
| qs_0017 | experience_screen | What is your predicted/final degree classification? | 26 | graphcore, graphcore-early-careers |
| qs_0094 | work_authorization | Are you legally authorized to work lawfully in the U.S.? | 26 | duolingounirecruitment, thenuclearcompany |
| qs_0020 | logistics | From where do you intend to work? | 25 | figma |
| qs_0022 | factual_profile | Have you ever worked for Figma before, as an employee or a contractor/consultant? | 25 | figma |
| qs_0023 | factual_profile | Who is your current or previous employer? | 25 | stripe |
| qs_0025 | logistics | What country are you based in? | 25 | brex |
| qs_0027 | logistics | Do you currently live in, or plan to relocate to, the specified location to meet this in-office requirement? | 25 | brex |
| qs_0028 | logistics | This role requires in-office work three days per week (Mon, Wed, Thurs). Do you acknowledge and agree to this requirement? | 25 | brex |
| qs_0029 | factual_profile | Do you currently, or have you previously, worked at Capital One or a company acquired by Capital One as an employee, contractor, consultant, or temp? (For example Capital One Bank, N.A., Capital One Services, Inc., Chevy Chase Bank, Discover, Hibernia, ING Direct, North Fork Bank) | 25 | brex |
| qs_0030 | legal_screen | If you currently work, or have previously worked, at Capital One or a company acquired by Capital One, please provide your Employee ID (EID). This information is required for former/current employees. | 25 | brex |
| qs_0031 | legal_screen | Are you currently subject to any agreement with a former employer/third party (such as a non-solicitation or non-compete agreement) that may potentially limit your ability to perform the duties of the position you are applying for? If yes, you may be asked to provide a copy for review. Please note, answering "yes" will not disqualify your application from consideration. | 25 | chime |
| qs_0032 | logistics | In which country/region are you currently based? | 25 | agoda |
| qs_0033 | factual_profile | Do you currently or have you previously worked for another Farm Credit association other than Compeer Financial? | 25 | compeerfinancial |
| qs_0034 | logistics | Are you open to relocating for this position, or are you currently within driving distance of the position location? | 25 | compeerfinancial |
| qs_0035 | factual_profile | Have you worked for the U.S. Department of Defense (DoD) within the past two (2) years in a role that may be subject to post-government employment restrictions (Sec. 847 30-day letter)? If you have not worked for the DoD in the past two (2) years, please select “No.” Otherwise, please review the information below before selecting your response. | 25 | divergent |
| qs_0037 | factual_profile | Have you worked at DoorDash? | 25 | doordashusa |
| qs_0038 | factual_profile | Would you like to receive communications via SMS and/or WhatsApp to the number provided [above or during the application process] about your application process? Message & data rates may apply and message frequency may vary. If you select no, we will only communicate with you via email and/or telephone calls. If you select yes and change your mind, you can always reply STOP to opt out. | 25 | doordashusa |
| qs_0039 | logistics | This role is designated as on-site and requires working from the office five days per week. Can you meet this requirement? | 25 | fanaticscollectibles |
| qs_0041 | work_authorization | Are you able to provide proof of your legal work authorization? | 25 | fanaticscollectibles |
| qs_0044 | logistics | This job requires access to export-controlled information, a condition of which, absent certain exceptions, is US person status. Please confirm whether you are a (1) US Citizen, (2) Lawful Permanent Resident, or (3) Qualifying Asylee. | 25 | generalmatter |
| qs_0045 | logistics | To conform to U.S. Government space technology export regulations, including the International Traffic in Arms Regulations (ITAR) you must be a U.S. citizen, lawful permanent resident of the U.S., protected individual as defined by 8 U.S.C. 1324b(a)(3), or eligible to obtain the required authorizations from the U.S. Department of State. Do you meet the above criteria? | 25 | inversionspace |
| qs_0047 | work_authorization | U.S. Export Control laws require that access to certain technical information be limited to U.S. Persons (U.S. Citizens and Lawful Permanent Residents/Green Card Holders) and individuals granted appropriate authorization. Please indicate your current Immigration and Work Authorization status. Verification will be required upon hire. | 25 | muonspace |
| qs_0048 | factual_profile | Please provide a link to your personal or professional website (optional). | 25 | scoutmotors |
| qs_0049 | experience_screen | Do you have experience in manufacturing, OEM, Tier I supplier, or automotive industries? | 25 | scoutmotors |
| qs_0050 | logistics | Which Scout Motors location are you closest to? | 25 | scoutmotors |
| qs_0052 | logistics | What is your current state of residence? | 25 | scoutmotors |
| qs_0053 | factual_profile | Are you currently employed by, or have you previously been employed by, Volkswagen Group or any of its subsidiaries, including but not limited to Scout Motors, Audi, Porsche, Bentley, Ducati, CUPRA, SEAT, or ŠKODA? | 25 | scoutmotors |
| qs_0054 | factual_profile | Do you have any professional or personal connections to individuals currently employed by Scout Motors or any of its subsidiaries or related entities (for example, Volkswagen Group companies), including relationships as a colleague, friend, or family member? | 25 | scoutmotors |
| qs_0055 | legal_screen | Are you subject to any restriction that could prevent or limit your ability to work for Scout Motors (e.g., non-compete agreement with your former employer)? | 25 | scoutmotors |
| qs_0056 | behavioral | Do you have any conflicts of interest that could affect your ability to perform the duties of the role you are applying for at Scout Motors, including financial interests held by you or your immediate family in competitors, vendors, or clients relevant to this role, or any personal or professional relationships that could create a conflict? Please describe any such conflicts. | 25 | scoutmotors |
| qs_0058 | logistics | The previous question addressed citizenship in certain countries subject to contractual restrictions. In addition to U.S. citizenship, do you currently hold citizenship in any other country (including dual or multiple citizenship)? | 25 | stratolaunch |
| qs_0062 | factual_profile | If you've selected "Yes", please select the affiliate/subsidiary with which you were employed: | 25 | thenewyorktimes |
| qs_0063 | work_authorization | Are you legally authorized to work in the Country specified for this position? | 25 | thenewyorktimes |
| qs_0064 | legal_screen | Do you have any relatives, spouses, partners or in-laws currently employed at The New York Times? | 25 | thenewyorktimes |
| qs_0065 | logistics | Are you a U.S. citizen, U.S. lawful permanent resident, or protected individual as defined by the ITAR requirements stated above? | 25 | vardaspace |
| qs_0066 | factual_profile | Have you previously worked for Voyager or one of its subsidiaries? If so, when, which subsidiary, what position? | 25 | voyagertechnologiesinc |
| qs_0067 | compensation | What is your desired base compensation for this role? Note that this company also leverages equity as part of its compensation model. | 25 | oklo |
| qs_0068 | factual_profile | As we are majority owned by Tencent, we would like to know if you have worked for Tencent or a company owned or otherwise affiliated with Tencent within the last 12 months. | 25 | riotgames |

## What this is

- The full 2,176 corpus stays in `shared/question_bank_unique.yaml`.
- This semantic set is the proposed live bank: 10 seeds plus the
  generic clusters that survive the filter.
- Company-specific one-offs, consent fields and early-career fields are
  not in the live set. They remain in the corpus.
- Every row is still marked `needs_review: true`; the categories are a
  first pass.
