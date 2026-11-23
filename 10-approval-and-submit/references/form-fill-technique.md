# Form-Fill Technique — Zoho Recruit / Ashby ATS

## When to Use

You are driving an ATS application form via `computer_use` on Kenechukwu's desktop Chrome. The form is Zoho Recruit or Ashby (the two ATS platforms this pipeline encounters most). Manual field-by-field typing is failing — stale element indices, page auto-scroll, Chrome autofill interference, focus drift.

## The Golden Rule: Prefer Native Autofill

**Both Zoho Recruit and Ashby have a resume-upload autofill feature.** It parses the uploaded `.docx` and fills name, email, phone, current title, skills (as chips), education, and experience (with dates and summaries). This is vastly more reliable than 30+ synthetic clicks.

### Zoho Recruit Autofill
1. Scroll to the top of the form (the autofill dropzone is above the first section).
2. Click the **"Upload your resume or drag and drop it here"** box (`delivery_mode: foreground` on Chrome).
3. A native Windows **Open** dialog appears (window title "Open", separate PID from Chrome).
4. Click the **File name** edit box in that dialog, type the **full absolute path** to the tailored `.docx`, press Enter, then click the **Open** button (or press Enter again).
5. Wait 3-5 seconds. Zoho shows a green banner: "Resume parsed successfully. Kindly review the extracted details before clicking Submit."
6. Verify: all Basic Info fields populated, Address section has the candidate's real saved address (if any), Professional Details has job title + skill chips, Education + Experience tables are filled.
7. **Only fill what autofill missed:** LinkedIn URL, State/Province (sometimes blank), CAPTCHA.

### Ashby Autofill
Similar flow: click the resume upload box → file dialog → full path → Open. Ashby parses and fills the same fields plus LinkedIn/GitHub if present in the resume header.

## If Autofill Is Not Available (or Fails)

### Chrome on Windows — Foreground Delivery Is Mandatory
- `browser_click`/`click` works in background.
- `browser_type`/`type` and `key`/`press_key` **require `delivery_mode: foreground`** — they will hard-fail with `background_unavailable` otherwise. Use foreground for every keystroke.
- Each foreground action briefly steals focus; accept this, it's the only way text lands.

### Element Indices Are Stale After Any Page Scroll
**Never reuse an index from a prior capture.** Pattern that works:
```
1. capture(som, max_elements=30)       # fresh indices
2. click(element=<index from THIS capture>)
3. type(..., delivery_mode: foreground)
4. capture(som, max_elements=10)       # verify it landed, fresh indices
```
If you must use coordinates, same rule: `capture → coordinate click → type → capture`.

### Defeating Chrome Saved-Address Autofill
Chrome injects a saved address dropdown (or a wrong Japanese one) into Street/Zip/State fields.
```
click(coord, delivery_mode: foreground)
key('Escape', delivery_mode: foreground)      # dismiss dropdown
key('ctrl+a', delivery_mode: foreground)      # select any existing text
type('correct value', delivery_mode: foreground)
```
Do this for every address field — the dropdown fights you on each one.

### CAPTCHA
Zoho Recruit shows a **text CAPTCHA** (distorted alphanumeric, e.g. "cecdx6").
1. `capture(vision)` on the viewport — the vision model reads the CAPTCHA image reliably.
2. Take **two independent reads** and confirm they match (this session: "cecdx6" ×2).
3. Click the CAPTCHA input box (foreground), type the text.

### Clicking Submit
The submit button is a purple "Submit Application" button. The `pre_tool_call` submit-gate hook watches for `computer_use`/`computer` tool names with `submit` substrings — it will veto unless `approval_decision='approve'` is in the DB row. The hook is in `security/hooks/verify-submit-approval.py` and its `WATCHED_TOOLS` includes `computer`, `computer_use`, `computer-use`.