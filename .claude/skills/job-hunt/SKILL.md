---
name: job-hunt
description: Set up and run the job search. Follow the companies in companies.yaml (add or remove them on the fly, building a reverse-engineered source for unsupported careers sites), fetch new roles, score them against the user's profile and keep a shortlist, and schedule daily runs. Hands off to /apply for tailoring and applying. Use when the user runs /job-hunt, asks to set up their profile, look for jobs, check for new openings, add/remove companies, or schedule runs.
argument-hint: "[setup | score | schedule | add <company> | remove <company> | <focus>]"
---

# Job hunt

The `jobhunt` CLI (run `uv run jobhunt …` from the repo root) does the deterministic work:
fetching postings, storing state in SQLite, digests and schedules. You do the judgment:
setting up the profile and scoring roles. Applying is a separate skill, `/apply`.

The arguments the user passed pick the mode:

| Argument | Mode |
|---|---|
| none, or a focus ("only ML roles") | Interactive run: steps 0 to 3 |
| `setup`, `setup profile` | Step 0 only |
| `add <company>` / `remove <company>` | Step 1.1 only |
| `score` | **Unattended**: see "Unattended scoring" below |
| `schedule` | Step 4 |

## 0. Setup (first run, or whenever something is missing)

Check from the repo root, and fix only what's missing:

1. **Tooling.** `uv --version`. If it fails, ask the user to install uv
   (https://docs.astral.sh/uv/). Then run `uv sync`.
2. **Companies.** If `uv run jobhunt companies` says there's no companies.yaml, ask which
   companies the user wants to follow and add each one (step 1.1). Offer
   `companies.example.yaml` as a starting point. Don't copy it silently: the list is theirs.
3. **Profile.** If `profile/profile.yaml` or `profile/master_facts.md` is missing:
   - Offer to draft them from the user's CV or LinkedIn export (a file path, or pasted text).
     Put **every** fact from it into master_facts.md, one bullet per achievement, keeping
     numbers exactly as written. Draft profile.yaml from the CV plus the answers to: target
     roles and seniority, locations (remote/relocation), work authorisation, notice period
     and salary expectation (blank is fine).
   - Show both files and ask the user to correct them. Never invent a fact to fill a gap.
   - If they don't want to share a CV, point to the `.example.` files.
   - Discovery runs on the example profile (with a warning), but **never score for real,
     tailor or apply from example data.**
4. Read both profile files fully before scoring. They are the only source of facts about the user.

## 1. Companies and discovery

1. **Adding a company:** `uv run jobhunt add "<Name>" [--url <careers url>] --json`. This
   resolves built-in presets (`uv run jobhunt sources` lists Apple, Google, DeepMind, Meta,
   Microsoft and more) and auto-detects Greenhouse, Lever and Ashby boards.
   - If the result has `how: "name_guess"`, the board was guessed from the name alone. Tell the
     user the board slug and a couple of its job titles, and ask them to confirm it's the right
     company before going on.
   - **Removing:** `uv run jobhunt remove <key>`. **Pausing:** set `enabled: false` in companies.yaml.
   - If `add` returns `added: false`, the careers site needs a new source. Tell the user, then:
     - For a one-off, browse the careers page directly this run, or use `/apply <link>` for a
       single posting.
     - To make it permanent, offer to build a source following `docs/adding-a-source.md` (repo
       root). That needs the `reverse-api-engineer` CLI: check `reverse-api-engineer --version`,
       and **ask before installing** it (`uv tool install reverse-api-engineer`). A capture
       costs model usage (about 1 to 2.50 USD per site), so say so and get a yes first. If the
       `reverse-api-engineer` skill is installed, follow it for the capture. Otherwise use the
       commands in the doc. Ask whether it's **personal** (default: `local_sources/<name>.py`,
       gitignored, absolute imports) or a **contribution** to the shared repo
       (`src/jobhunt/sources/`). Port the client there, add a fixture test next to it
       (`local_sources/test_<name>.py` or `tests/test_sources.py`), and run `jobhunt add` again.
2. `uv run jobhunt discover --json` (or `discover <key> …` for a subset). Report errors per
   company but carry on, since one broken source must not stop the run. An error from a
   reverse-engineered source usually means the site changed: offer to re-capture it.

## 2. Score

1. `uv run jobhunt jobs --status new --json` lists the candidates (descriptions omitted).
2. First pass on title, team and location against `preferences` in profile.yaml. Roles that
   are clearly out (wrong function, wrong seniority) can be skipped on the title alone. For
   plausible ones, read the full description: `uv run jobhunt show <uid> --json`.
3. Score each role 0–100 for fit: seniority, must-haves, nice-to-haves, avoid, location, and
   **evidence in master_facts** (a requirement the facts don't support lowers the score).
   Record every decision so it isn't re-scored next time:
   - `uv run jobhunt status shortlisted <uid> --score N --notes "<one-line why>"` when N ≥ `min_score_to_shortlist`
   - `uv run jobhunt status skipped <uid> --score N --notes "<why not>"` otherwise

## 3. Shortlist and hand off

Show the user a compact table of the shortlist (score, company, title, location, why), best
first. Then say how to continue: `/apply` works through the shortlist (or `/apply <uid> …`
for specific ones). Don't tailor or apply from this skill.

## Unattended scoring (`/job-hunt score`)

This mode runs from cron with nobody watching (`jobhunt schedule add --task score`), with
access limited to reading files and running `uv run jobhunt`. In this mode:

- Don't ask questions, add companies, browse, edit files or install anything.
- If profile.yaml or master_facts.md is missing, stop and print that setup is needed.
- Run step 2 on the `new` roles only. Discovery has already run.
- Never prepare, tailor or apply. Finish with `uv run jobhunt digest --write` and a
  three-line summary (new, shortlisted, skipped).

## 4. Schedule (`/job-hunt schedule`)

Help the user put discovery on a timer. Show the current state with `uv run jobhunt schedule list`.
Then ask what they want and run one of these (try `--dry-run` first and show the line):

- **Free daily check:** `uv run jobhunt schedule add --task discover --at 08:30 --days weekdays --notify`.
  This fetches new roles and writes `data/digests/<date>.md`. No model usage.
- **Daily check plus scoring:** `uv run jobhunt schedule add --task score --at 08:30 --notify`.
  Claude scores new roles headlessly, so the shortlist is ready when they sit down. This uses
  model usage on every run, so say so. It needs a working `claude` CLI: if `claude --version`
  fails in a terminal, point them to the install docs or `--claude <path>`.
- **Remove:** `uv run jobhunt schedule remove <name>`.

Explain the limits plainly:
- Cron only runs while the computer is awake. A missed run happens at the next scheduled time, not on wake.
- Scheduled runs never apply. Applying always goes through `/apply` with their approval.
- On macOS the first run may prompt for permissions. Logs are in `data/logs/scheduled.log`.

## Notes

- Sources: greenhouse/lever/ashby use public job-board APIs. eightfold (Microsoft), apple,
  google, meta and the others are reverse-engineered clients of the careers sites' internal
  endpoints and can break when those sites change. Each module's docstring lists the
  endpoints it relies on.
- Don't automate LinkedIn (Easy Apply automation gets accounts banned).
- Keep request rates polite. `discover` once per run is enough.
