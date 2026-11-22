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
- Check `apply.max_applications_per_company_per_week` with
  `uv run jobhunt jobs --status applied --company <key> --json`. If a role would exceed it,
  say so and skip that role unless the user overrides.
- PDFs need the optional extra. If `render` reports `playwright not installed`, ask once
  before running `uv sync --extra pdf && uv run playwright install chromium`
  (about 150 MB download).

## 2. Tailor (per role, in its application folder)

The folder has `jd.md` (the posting), `job.json`, and for Greenhouse roles `questions.md`
(the form's actual questions).

1. **`cv.md`:** a one- to two-page CV in markdown. Use `# Name`, then `## Summary`,
   `## Experience` (each role as `### Title — Company (City) · dates` with bullets),
   `## Education` and `## Skills`. Rules:
   - **Select, reorder and rephrase only.** Every claim, number, skill, title and date must
     trace to master_facts.md. Never add a skill, tool or metric that isn't there, even if
     the job wants it. A missing requirement is a gap, not something to paper over.
   - Lead with the experience most relevant to this job. Mirror its vocabulary only where it
     honestly describes what the user did.
   - Respect the "Do not mention" section.
2. **`cover_letter.md`:** write one when the form asks for it, has an optional upload, or the
   user wants one. Three or four short paragraphs: why this team or problem (specific to
   the posting), the two or three most relevant pieces of evidence, a plain close. No
   clichés, and the same no-fabrication rule. Sign off with the user's name.
3. **`answers.md`:** draft answers to the form's free-text questions (from `questions.md`,
   or found while filling in step 4) using master_facts and profile.yaml → `application`.
4. **`tailoring.md`:** what you emphasised and why, what you left out, gaps against the
   posting, and any claim you weren't sure was supported. Keep it short. The user reads it
   at approval time.
5. `uv run jobhunt render <dir> --json` produces `cv.pdf` and `cover_letter.pdf`. Open the
   PDF and check the CV fits two pages at most. Tighten it if not.
6. `uv run jobhunt status drafted <uid>`.

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

1. Open `apply_url` from job.json (or `url`, then its Apply button).
2. Fill the standard fields from `profile.yaml → me` and `application` (name, email, phone,
   links, work authorisation, notice, demographics as configured). Upload `cv.pdf`, and
   `cover_letter.pdf` where there's a slot. Paste the answers from `answers.md`.
3. Login, account creation, captcha or 2FA (Workday, and the Apple, Google, Microsoft and
   Meta portals all need accounts): pause and hand over to the user, then continue once they
   say it's done. Never try to get around one.
4. Check the filled form against `answers.md` and the profile, especially email, phone and
   the uploaded file names.
5. Screenshot the completed form to `pre-submit.png` in the folder and **stop**. Don't
   press submit. `uv run jobhunt status ready <uid>`.

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
- The user's personal data stays in `profile/` and `applications/`, both gitignored. Never
  copy it anywhere else in the repo.
