# Contributing

Thanks for helping. The most useful contributions are new **sources** (careers platforms and
sites) and fixes when an existing reverse-engineered source breaks.

## Setup

```bash
uv sync --extra dev
uv run pytest -q                              # offline tests
uvx ruff check src tests                      # lint
JOBHUNT_LIVE=1 uv run pytest -m live -v       # hits the real careers sites
```

## Adding or fixing a source

Follow [docs/adding-a-source.md](docs/adding-a-source.md). A source PR should include:

- the module in `src/jobhunt/sources/`, with a docstring naming the endpoints it relies on
- `PRESETS` if it serves specific companies, and `COMPLETE_LISTING = True` only if it returns
  every open role
- an offline fixture test in `tests/test_sources.py` and a case in `tests/test_live.py`
- **no** HAR files, `rae*.ndjson` / `rae*.log`, cookies or tokens

Prefer platform sources (one per ATS, e.g. Workday) over per-company ones.

## Ground rules

- Read-only access to public job listings, at polite rates. No bypassing captchas, logins
  or rate limits, and no automating LinkedIn.
- Keep the approval gate: nothing may submit an application without explicit user approval.
- Keep personal data out of the repo. `companies.yaml`, `profile/`, `applications/` and
  `data/` stay gitignored.
