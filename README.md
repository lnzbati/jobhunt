# jobhunt

Follow the companies you care about, get the new roles that fit you, tailor a CV and cover
letter for each from a single source of truth, and fill in the applications. Nothing is
submitted until you approve it.

It's a [Claude Code](https://claude.com/claude-code) skill (`/job-hunt`) on top of a small
Python CLI:

| Part | Does |
|---|---|
| `jobhunt` CLI | Fetches postings, filters them, stores state in SQLite, creates application folders, renders PDFs. Deterministic, no model calls. |
| `/job-hunt` skill | Claude scores roles against your profile, tailors your CV and cover letter (no fabrication), fills in forms in your browser, and stops for approval before each submit. It also builds new sources for unsupported careers sites. |

## Prerequisites

| Needed for | What |
|---|---|
| Everything | [uv](https://docs.astral.sh/uv/) (it installs Python 3.11+ for you) |
| The `/job-hunt` skill | [Claude Code](https://claude.com/claude-code) |
| Applying | A browser tool Claude Code can drive in your signed-in browser: [gstack](https://github.com/garrytan/gstack) `/browse`, Claude in Chrome, or a Playwright MCP. Without one, the skill prepares everything and you submit by hand. |
| PDF output (optional) | `uv sync --extra pdf && uv run playwright install chromium`. Otherwise you get HTML. |
| New custom-site sources (optional) | [reverse-api-engineer](https://github.com/kalil0321/reverse-api-engineer): `uv tool install reverse-api-engineer` (needs Node.js 20.19+). Only needed to support a careers site the built-in sources don't cover. The skill asks before installing it. |

## Quick start

```bash
git clone https://github.com/lnzbati/jobhunt.git && cd jobhunt
uv sync

# 1. Companies: add by name (companies.yaml is created and gitignored)
uv run jobhunt add Apple                 # built-in source
uv run jobhunt add Monzo                 # Greenhouse/Lever/Ashby board detected automatically
uv run jobhunt add Stripe --url https://job-boards.greenhouse.io/stripe   # exact board from a URL
#    ...or start from the example list
cp companies.example.yaml companies.yaml

# 2. Profile (both gitignored)
cp profile/profile.example.yaml profile/profile.yaml
cp profile/master_facts.example.md profile/master_facts.md
```

Then, in Claude Code from this directory, run `/job-hunt`. On first run it checks what's
missing and can draft your profile from your CV.

## Configuration

All three files are yours and gitignored. Only the `.example` versions are tracked.

**`companies.yaml`**: who to follow. Manage it with the CLI or edit it by hand.
[`companies.example.yaml`](companies.example.yaml) documents the format.

```bash
uv run jobhunt companies                 # what you follow
uv run jobhunt sources                   # available sources + built-in presets
uv run jobhunt add "<Name>" [--url <careers page>] [--key <id>]
uv run jobhunt remove <key>              # or set `enabled: false` to pause
```

**`profile/profile.yaml`**: contact details, what to look for, how to score, standard form
answers. Its sections:

- `search`: queries for the big search-based sites, title include/exclude lists, locations,
  and which remote regions count.
- `search.site_filters.<company key>`: server-side filters for the big sites, for example
  Apple's location slug, Google's location and Microsoft's location. Those sites list tens of
  thousands of roles, so they are searched rather than crawled.
- `preferences`: what Claude scores against (seniority, target roles, must-haves, what to avoid).
- `application`: answers reused verbatim in forms (work authorisation, notice period,
  salary, demographics).
- `apply`: the approval gate and per-company weekly cap.

**`profile/master_facts.md`**: every claim you can stand behind. Tailoring may select,
reorder and rephrase from it, but never add to it.

## Sources

| Source | Covers | How |
|---|---|---|
| `greenhouse` | any company on Greenhouse | Public Job Board API |
| `ashby` | any company on Ashby | Public Job Posting API |
| `lever` | any company on Lever | Public Postings API |
| `eightfold` | Eightfold.ai sites (preset: Microsoft) | Public `pcsx` JSON API (reverse-engineered) |
| `apple` | Apple | Hydration JSON in search and details pages (reverse-engineered) |
| `google` | Google, DeepMind, YouTube (presets: google, deepmind) | `AF_initDataCallback` page data (reverse-engineered) |
| `meta` | Meta | Relay GraphQL persisted query + CSRF token; recovers a rotated `doc_id` itself (reverse-engineered) |

The reverse-engineered sources were captured with reverse-api-engineer and then hardened by
hand. Each module's docstring lists the endpoints it relies on, and `tests/test_sources.py`
pins the parsing assumptions.

**Careers site not covered?** Workday, SmartRecruiters, bespoke sites and so on: see
[docs/adding-a-source.md](docs/adding-a-source.md), or ask `/job-hunt` to add the company and
it will offer to build the source. A new source is one file in `src/jobhunt/sources/`, picked
up automatically. PRs welcome.

## CLI reference

```bash
uv run jobhunt discover [<key> ...]          # fetch, prefilter, store; reports per-company errors
uv run jobhunt jobs [--status new|...|all] [--company <key>] [--since 2026-11-01] [--full]
uv run jobhunt show <uid>                    # full description (fetched on demand)
uv run jobhunt status <status> <uid>... [--score N] [--notes "..."]
uv run jobhunt prepare <uid>                 # applications/<date>-<company>-<role>/ with jd.md, job.json
uv run jobhunt render <application dir>      # cv.md / cover_letter.md -> PDF (or HTML)
```

Add `--json` to any command for machine-readable output. Pipeline statuses:
`new → shortlisted → drafted → ready → applied` (or `skipped`; roles that disappear from a
board become `closed`).

## Design choices

- **Approval before every submit.** Applications can't be withdrawn, and recruiters notice
  batches of near-identical ones. The skill fills in the form, saves a screenshot and waits.
- **No fabrication.** Every tailored claim must trace to `master_facts.md`, and gaps are reported
  rather than papered over.
- **No captcha solving, no LinkedIn automation.** Captchas, logins and account creation are
  handed back to you.
- **Reading via APIs, applying via the browser.** ATS submit endpoints need employer API keys
  and are protected against bots. Filling the real form in your own browser is reliable and
  within the sites' rules.
- **Polite.** One `discover` per run, capped pagination, and delays between pages.

## Responsible use

- The built-in custom-site sources read the same **public job listings** those sites show
  to any visitor, through the endpoints their own pages call. They aren't official APIs:
  check each site's terms yourself, keep request rates low, and expect them to change.
- Applications go out under your name. Review every one. The tool is built to stop
  before submitting, so keep it that way.
- This project isn't affiliated with or endorsed by any company it supports.

## Contributing

New sources and fixes are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Quick checks:

```bash
uv run --extra dev pytest -q                 # offline
JOBHUNT_LIVE=1 uv run --extra dev pytest -m live -v   # real sites (also runs weekly in CI)
```

## Privacy

`companies.yaml`, `profile/`, `applications/` and `data/` are gitignored. Never commit HAR
captures or reverse-api-engineer logs: they can contain cookies.

## Licence

MIT
