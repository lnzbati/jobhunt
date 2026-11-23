---
name: apply
description: Apply to jobs for the user. With no argument, works through the shortlisted roles; with a job-posting link (any careers site), imports that single role. For each role it tailors a CV and cover letter from master_facts.md (never inventing facts), renders PDFs, fills in the application form in the user's browser, and submits only after the user explicitly approves that specific application. Use when the user runs /apply, asks to apply to roles, or shares a job link to apply to.
argument-hint: "[job posting URL | job uid ... | resume]"
---

# Apply

Turns roles into submitted applications: **tailor, render, fill, approve, submit.** Nothing
is submitted without the user's explicit approval for that specific application.

Run everything from the repo root with `uv run jobhunt …`.

## 0. Which roles

Look at the arguments the user passed:

| Argument | Roles to work on |
|---|---|
| a URL | **Single application.** `uv run jobhunt import "<url>" --json` stores the role as shortlisted and creates its folder. Then follow the "From a link" notes below. |
| one or more job uids (`company:id`) | Those roles: `uv run jobhunt prepare <uid> --json` for each. |
| `resume` | Roles already `ready` (forms filled, waiting for approval): go straight to step 5. |
| nothing | The shortlist: `uv run jobhunt jobs --status shortlisted --json`. Show it (score, company, title, why) and ask which to apply to now. Default to none, and don't start until they pick. |

**From a link:**
- If `import` fails, read the posting in the browser and tell the user. Don't guess the job.
- If `previous_status` is `applied`, stop. Tell the user they already applied, and when.
- If `needs_review` is true, the posting was read from raw page text. Open the link in the
  browser, read the actual job description, and replace the description in `jd.md` with it
  before tailoring. If the link is a list of jobs rather than one posting, ask which role.
- A link to a company you don't follow is fine. Don't add the company unless asked.

## 1. Before tailoring

- `profile/profile.yaml` and `profile/master_facts.md` must exist and not be the examples.
  If they're missing, stop and point to `/job-hunt setup`.
- Read both fully. They are the **only** source of facts about the user.
- If `profile/apply-notes.md` exists, read it too. It holds the user's own notes about specific
  sites (sign-in quirks, button labels, fields to double-check). Follow them, unless they
  conflict with "Rules that always hold".
- Check `apply.max_applications_per_company_per_week` with
  `uv run jobhunt jobs --status applied --company <key> --json`. If a role would exceed it,
  say so and skip that role unless the user overrides.
- PDFs need the optional extra. If `render` reports `playwright not installed`, ask once
  before running `uv sync --extra pdf && uv run playwright install chromium`
  (about 150 MB download).

## 2. Tailor (per role, in its application folder)

The folder has `jd.md` (the posting), `job.json`, and for Greenhouse roles `questions.md`
(the form's actual questions).

Most employers screen CVs with an applicant tracking system (ATS) that extracts the text and
searches it for the job's key terms. Tailoring is built around that, **without ever adding
claims the facts don't support.**

1. **`keywords.md`: the job's key terms.** Read `jd.md` and list the 10–25 terms a recruiter
   would search for: skills, tools, methods, domain terms and certifications, in the posting's
   own wording. One per line. Put alternatives after `|` (`Kubernetes | k8s`,
   `stakeholder management | stakeholders`), and mark must-haves from the requirements with
   `!`. Skip soft filler like "team player" and "fast-paced".
2. **ATS plan:** `uv run jobhunt ats <dir> --plan --json` sorts the terms into:
   - **supported**: in master_facts. The CV should use these, in the job's exact wording
     where it honestly describes the fact (e.g. the facts say "led migration to streaming
     pipelines" and the job says "data pipelines": write "data pipelines").
   - **gaps**: not in the facts. **Don't add them.** Note them in tailoring.md, and check the
     facts for a real equivalent under other wording before calling something a gap. A
     must-have gap is worth telling the user about before they spend time applying.
3. **`cv.md`:** a one- to two-page CV in markdown. Use `# Name`, then `## Summary`,
   `## Experience` (each role as `### Title — Company (City) · dates` with bullets),
   `## Education` and `## Skills`. Rules:
   - **Select, reorder and rephrase only.** Every claim, number, skill, title and date must
     trace to master_facts.md. Never add a skill, tool or metric that isn't there, even if
     the job wants it. A missing requirement is a gap, not something to paper over.
   - Lead with the experience most relevant to this job. Mirror its vocabulary only where it
     honestly describes what the user did.
   - Work each supported term into a real bullet, not only the Skills line. ATSs and recruiters
     both weigh terms that appear in context.
   - ATS-safe layout: keep the standard section names above, plain bullets, no tables, columns,
     icons or images. Write dates as `Mon YYYY – Mon YYYY` (or `– Present`) when the facts have
     months, otherwise `YYYY – YYYY`. Spell out an acronym once with its expansion when the job
     uses the other form ("Site Reliability Engineering (SRE)").
   - Respect the "Do not mention" section.
4. **`cover_letter.md`:** write one when the form asks for it, has an optional upload, or the
   user wants one. Three or four short paragraphs: why this team or problem (specific to
   the posting), the two or three most relevant pieces of evidence, a plain close. No
   clichés, and the same no-fabrication rule. Sign off with the user's name.
5. **`answers.md`:** draft answers to the form's free-text questions (from `questions.md`,
   or found while filling in step 4) using master_facts and profile.yaml → `application`.
6. **`tailoring.md`:** what you emphasised and why, what you left out, gaps against the
   posting, and any claim you weren't sure was supported. Keep it short. The user reads it
   at approval time.
7. `uv run jobhunt render <dir> --json` produces `cv.pdf` and `cover_letter.pdf`, plus copies
   named after the user (`First-Last-CV.pdf`). **Upload the named copies**, because recruiters
   see the file name.
8. **ATS check:** `uv run jobhunt ats <dir> --json` reads `cv.pdf` the way an ATS does and
   writes `ats.md`. Fix and re-render until:
   - no parsing check fails (contact details extract intact, standard headings, no ligatures
     or icon glyphs) and the CV is two pages at most;
   - the "in your facts but not in the CV" list is empty, or each remaining term was left out
     on purpose (say why in tailoring.md).

   Never chase coverage by adding gap terms. A truthful 60% beats an invented 100%, and gaps
   are what the interview will probe. Put the coverage figure and the remaining gaps at the
   top of tailoring.md.
9. `uv run jobhunt status drafted <uid>`.

**AI-use policies.** Some employers ask candidates not to use AI for parts of the
application. Anthropic's form does this, for example. If the posting or form states such a
policy, follow it. Don't draft the answers it covers: mark them in `answers.md` as "write
this yourself (employer AI policy)" and list them as open questions. Never tick an
attestation on the user's behalf.

## 3. Open questions

Some answers can't come from the profile: salary for a new country, a new visa situation,
"Are you willing to…?", referral names, attestations. Collect them per role and ask the user
in one batch before filling in forms. **Never guess them.** If the user doesn't answer, leave
those fields blank.

## 4. Fill in the form (stop before submitting)

Use a browser tool that works in the user's real, signed-in browser. Follow any browser
preference in the user's own instructions (CLAUDE.md). Otherwise use whichever is available:
gstack `/browse`, Claude in Chrome, or a Playwright MCP. With no browser tool, stop here and
give the user the folder (PDFs plus answers.md) and the apply URL to submit by hand.

**The user must be able to see and type into that browser** whenever they may need to step in
(sign-in, codes, captcha). If the tool runs headless, switch to a visible or signed-in mode
first (for gstack: `/open-gstack-browser` or `/setup-browser-cookies`). Otherwise there's
nothing for the user to type into.

1. Open `apply_url` from job.json (or `url`, then its Apply button).
2. If the site asks you to sign in or create an account, follow "Sign-in and accounts" below.
3. Work through the application **one screen at a time** ("Step-by-step forms" below). Fill
   the standard fields from `profile.yaml → me` and `application` (name, email, phone,
   links, work authorisation, notice, demographics as configured). Upload the named CV PDF
   (`First-Last-CV.pdf`), and the named cover letter where there's a slot. Paste the answers from `answers.md`.
4. Check everything against `answers.md` and the profile before the end, especially email,
   phone, the uploaded file names, and any answers the site pre-filled.
5. On the final review page (or the completed form, for single-page forms), screenshot to
   `pre-submit.png` in the folder and **stop**. Don't press submit.
   `uv run jobhunt status ready <uid>`.

### Step-by-step forms

Many portals show one field or one page at a time: email → Next → name → Next → … Fields
further on don't exist yet, so filling everything at once fails. Repeat until you reach the
final review page:

1. **Read the current screen** (fresh snapshot). Fill only the fields that are visible now.
2. **Press that screen's own button** (Next, Continue, Save and continue). Never press the final
   Submit or Apply: that waits for approval (step 5).
3. **Wait for the screen to change**: a new field, heading or URL. Take a fresh snapshot before
   typing again. Element references from the previous screen are stale.
4. **If it didn't move on**, read the validation message, fix that field, and retry. After two
   failed attempts on the same screen, stop and show the user the message.

Things that commonly go wrong on these portals:

- **Answers pre-filled from an earlier application** (old CV file, start date, salary,
  relocation, "how did you hear", demographics, consents). Never accept them as they are.
  Compare each one with the profile and this application, and fix any that differ. On a review
  page, expand every collapsed section before checking.
- **Fields that appear after a change**: picking an option can reveal a follow-up question.
  Re-read the screen after every change.
- **Dropdowns and dates**: after setting a dropdown, read the value back to confirm it took.
  Type dates in the format the field's placeholder shows.
- **Repeated questions**, such as consent or AI-use preferences, can come up on several steps.
  Answer them the same way each time, from the profile or the user.
- **Progress is saved as you go** on many portals. After each completed page, note the step in
  `progress.md` in the folder, so `/apply resume` carries on from there.

### Sign-in and accounts

Many portals need an account before you can apply. With the user present:

- **You fill the identity fields** one screen at a time from `profile.yaml → me`: email, first
  and last name, phone, country.
- **The user types passwords.** Never ask for a password in chat, store one, or write one to a
  file.
- **One-time codes** (email or SMS): pause and ask the user to type the code into the page, or
  paste it in chat. Don't open their inbox to fetch it unless they explicitly ask in that run.
- **Captcha, "are you a robot", passkeys, 2FA:** hand over and wait until the user says it's
  done. Never try to get around one.
- **Sign-in redirects**: some portals pass through intermediate pages after sign-in. Don't
  navigate away mid-redirect. Wait until the application form is showing.
- **Creating a new account** signs the user up to that site's terms: confirm once per site.
- **Once signed in**, reuse the same browser session for the other applications on that site.

### Site notes

When a run teaches you something specific to a site (exact button labels, a redirect to wait
out, a field that's always pre-filled wrongly, the selector for an upload input), add it under
that site's heading in `profile/apply-notes.md`, with the date. Create the file from
`profile/apply-notes.example.md` if it doesn't exist. It's private (gitignored) and is read
at the start of every `/apply`. Keep personal data out of it: notes about the site, not answers.

## 5. Approval and submit

Present each `ready` application:
- company, role, folder path
- the highlights from `tailoring.md` (emphasis and gaps)
- the answers given, and anything left blank
- the screenshot

Ask which to submit (for example "submit 1 and 3"). Submit **only** the ones the user
explicitly approves, in this conversation, for that specific application. A general "go
ahead" earlier doesn't count. For each approved one:

1. Re-open the filled form (or re-fill it if the session expired), press submit, and wait
   for the confirmation page or message. Save its text to `confirmation.txt`.
2. `uv run jobhunt status applied <uid> --notes "<confirmation ref or date>"`.

If submission fails or the outcome is unclear, **don't retry blindly**. Report what happened,
leave the status as `ready`, and let the user check (they may have received a confirmation email).

## 6. Wrap up

Summarise: applied (with folders), ready and waiting, drafted, skipped (and why), and any
open questions still waiting on the user.

## Rules that always hold

- No fabrication, in the CV, the letter, answers or form fields.
- No submission without explicit, per-application approval.
- No captcha solving, no getting around logins, no automating LinkedIn.
- Passwords are typed by the user only: never requested in chat, stored or written to a file.
- The user's personal data stays in `profile/` and `applications/`, both gitignored. Never
  copy it anywhere else in the repo.
