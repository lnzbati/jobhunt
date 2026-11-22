---
name: job-hunt
description: Find new roles at the companies in companies.yaml (add or remove companies on the fly, building a reverse-engineered source for unsupported careers sites), shortlist them against the user's profile, tailor a CV and cover letter from master_facts.md, fill in the application form in the browser, and submit only after explicit approval. Use when the user runs /job-hunt, asks to look for jobs, check for new openings, or apply to roles.
---

# Job hunt

The `jobhunt` CLI (run with `uv run jobhunt …` from the repo root) does the deterministic
work: fetching postings, storing state in SQLite, creating application folders and
rendering PDFs. You do the judgment: scoring, tailoring, and filling in forms.

Arguments the user may pass: companies to add or remove ("add Monzo", "drop Meta"), a role
focus ("only ML roles this time"), or a step to resume ("apply to the ones I approved").

## 0. Setup (first run, or whenever something is missing)

Check from the repo root, and fix only what's missing:

1. **Tooling.** `uv --version`. If it fails, ask the user to install uv
   (https://docs.astral.sh/uv/). Then run `uv sync`.
2. **Companies.** If `uv run jobhunt companies` says there's no companies.yaml, ask which
   companies the user wants to follow and add each one (step 1.1). Offer
   `companies.example.yaml` as a starting point. Don't copy it silently: the list is theirs.
3. **Profile.** If `profile/profile.yaml` or `profile/master_facts.md` is missing:
   - Offer to draft them from the user's CV or LinkedIn export if they share one. Put every
     fact from it into master_facts.md, then show both files for the user to correct.
   - Otherwise point to the `.example.` files.
   - Discovery runs on the example profile (with a warning), but **never score for real,
     tailor or apply from example data.**
4. Read both profile files fully before scoring. They are the only source of facts about the user.

## 1. Companies and discovery

1. **Adding a company:** `uv run jobhunt add "<Name>" [--url <careers url>] --json`. This
   resolves built-in presets (`uv run jobhunt sources` lists Apple, Google, DeepMind, Meta and
   Microsoft) and auto-detects Greenhouse, Lever and Ashby boards.
   - If the result has `how: "name_guess"`, the board was guessed from the name alone. Tell the
     user the board slug and a couple of its job titles, and ask them to confirm it's the right
     company before going on.
   - **Removing:** `uv run jobhunt remove <key>`. **Pausing:** set `enabled: false` in companies.yaml.
   - If `add` returns `added: false`, the careers site needs a new source. Tell the user, then:
     - For a one-off, browse the careers page directly this run.
     - To make it permanent, offer to build a source following
       [docs/adding-a-source.md](../../../docs/adding-a-source.md). That needs the
       `reverse-api-engineer` CLI: check `reverse-api-engineer --version`, and **ask before
       installing** it (`uv tool install reverse-api-engineer`). A capture costs model usage
       (about $1–2.50 per site), so say so and get a yes first. If the `reverse-api-engineer` skill
       is installed, follow it for the capture. Otherwise use the commands in the doc.
       Then port the client into `src/jobhunt/sources/`, add a fixture test, and run
       `jobhunt add` again.
2. `uv run jobhunt discover --json` (or `discover <key> …` for a subset). Report errors per
   company but carry on, since one broken source must not stop the run. An error from a
   reverse-engineered source usually means the site changed: offer to re-capture it.

## 2. Score and shortlist

1. `uv run jobhunt jobs --status new --json` lists the candidates (descriptions omitted).
2. Do a first pass on title, team and location against `preferences` in profile.yaml.
   For plausible roles, read the full description with `uv run jobhunt show <uid> --json`.
3. Score each role 0–100 for fit, considering seniority, must-haves, nice-to-haves, avoid
   and evidence in master_facts. Then record it:
   - `uv run jobhunt status shortlisted <uid> --score N --notes "<one-line why>"` when N ≥ `min_score_to_shortlist`
   - `uv run jobhunt status skipped <uid> --score N --notes "<why not>"` otherwise
4. Show the user a compact table of the shortlist (score, company, title, location, why)
   and **ask which ones to pursue**. Don't continue without their selection.

## 3. Tailor (for each selected role)

1. `uv run jobhunt prepare <uid> --json` creates `applications/<date>-<company>-<role>/`
   with `jd.md` and `job.json`.
2. Write `cv.md` in that folder: a one- to two-page CV in markdown (`## Experience`,
   `### Title — Company · dates`, bullets). Rules:
   - **Select, reorder and rephrase only.** Every claim, number, skill and date must trace
     to master_facts.md. Never add a skill or metric that isn't there, even if the job
     description wants it. If a key requirement isn't covered, list it as a gap instead.
   - Mirror the job description's vocabulary where it honestly applies.
   - Respect the "Do not mention" section.
3. Write `cover_letter.md` only if the form needs one or the user asked. Keep it to three or
   four short paragraphs, specific to the company and team, with no clichés and the same
   no-fabrication rule.
4. Write `tailoring.md`: what you emphasised, what you left out, gaps against the job
   description, and any claim you weren't sure was supported.
5. `uv run jobhunt render <dir> --json` produces PDFs (or HTML if Playwright isn't installed).
6. `uv run jobhunt status drafted <uid>`.

## 4. Fill in the form (stop before submitting)

Use a browser tool that works in the user's real, signed-in browser. Follow any browser
preference in the user's own instructions (CLAUDE.md). Otherwise use whichever is available:
gstack `/browse`, Claude in Chrome, or a Playwright MCP. If none is available, give the user
the folder (PDFs plus answers.md) and the apply URL to submit by hand.

1. Open `apply_url` from job.json.
2. Fill the standard fields from `profile.yaml → me` and `application`. Upload cv.pdf and
   cover_letter.pdf. For free-text questions, draft answers from master_facts and save them
   to `answers.md` in the folder.
3. If a question has no grounded answer in the profile (salary for an unusual country, a
   new visa situation, "Are you willing to…"), **leave it blank and add it to the open
   questions for the user**. Don't guess.
4. If there's a captcha, login, 2FA or account creation (Workday, and the Apple, Google,
   Microsoft and Meta portals all need accounts), pause and hand over to the user. Never
   try to get around one.
5. Take a screenshot of the completed form, save it as `pre-submit.png` and **stop**. Don't
   press submit yet. Mark the job `ready`.

Respect `apply.max_applications_per_company_per_week`. Check with
`uv run jobhunt jobs --status applied --company <key> --json`.

## 5. Approval and submit

Show the batch: for each `ready` role, the folder path, tailoring.md highlights, open
questions and the screenshot. Ask the user to approve each role (for example "submit 1, 3").
Only with explicit approval for that specific role (and `apply.require_approval` is
true by default):

1. Press submit, then wait for and save the confirmation page or text to `confirmation.txt`.
2. `uv run jobhunt status applied <uid> --notes "<confirmation ref if any>"`.

If submission fails or the outcome is unclear, **don't retry blindly**. Report it and leave
the status as `ready`.

## 6. Wrap up

Summarise: companies scanned, new roles, shortlisted, drafted, submitted, and anything waiting
on the user.

## Notes

- Sources: greenhouse/lever/ashby use public job-board APIs. eightfold (Microsoft), apple,
  google and meta are reverse-engineered clients of the careers sites' internal endpoints and
  can break when those sites change. Each module's docstring lists the endpoints it relies on.
- Don't automate LinkedIn (Easy Apply automation gets accounts banned).
- Keep request rates polite. `discover` once per run is enough.
