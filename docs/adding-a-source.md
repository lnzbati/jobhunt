# Adding a source for a custom careers site

Most companies don't need this. `jobhunt add "<Name>" --url <careers page>` handles any
company on Greenhouse, Lever or Ashby, plus the built-in sources (`jobhunt sources`).

You need a new source when `jobhunt add` reports `added: false`, meaning the careers site is
custom or uses an ATS we don't support yet (Workday, SmartRecruiters, Personio, Teamtailor,
iCIMS, SuccessFactors, …).

In Claude Code, `/job-hunt add <Company>` walks through all of this for you. The steps below
are what it does.

## 1. Check whether it's a platform we already cover

Before reverse-engineering anything, open the careers page and look at where its links and
requests go:

| You see | Do |
|---|---|
| `boards.greenhouse.io`, `jobs.lever.co`, `jobs.ashbyhq.com` | `jobhunt add "<Name>" --url <that URL>` |
| `*.eightfold.ai` or `/api/pcsx/` requests | add an `eightfold` entry with `base_url` and `domain` (see `companies.example.yaml`) |
| `myworkdayjobs.com`, `smartrecruiters.com`, … | write a **platform** source (step 2), so every company on that ATS benefits |
| A bespoke site | write a **company** source (step 2) |

## 2. Capture the site with reverse-api-engineer

Install the CLI once ([reverse-api-engineer](https://github.com/kalil0321/reverse-api-engineer),
needs Node.js 20.19+ for its browser tooling):

```bash
uv tool install reverse-api-engineer      # or: pipx install reverse-api-engineer
reverse-api-engineer --version
```

Preflight, then capture. Job listings are public, so `--headless` is enough:

```bash
GOAL="Fetch open job listings from <Company>'s careers site. Return title, job id, location(s), \
team, posting URL and posted date. Support keyword and location filters and full pagination. \
Prefer the underlying JSON/XHR API over HTML scraping. Also show how to fetch one job's full description."

reverse-api-engineer agent -p "$GOAL" -u "<careers search URL>" --headless --dry-run
reverse-api-engineer agent -p "$GOAL" -u "<careers search URL>" --headless --json-stream > rae.ndjson 2> rae.log
```

A run takes a few minutes and costs model usage (about $1–2.50 per site in our runs; the
final `result` line reports `usage.total_cost_usd`). Once it's done, `script_path` in that
line points to the generated client and its `README.md`.

To refine a capture without browsing again:
`reverse-api-engineer engineer <run_id> -p "also fetch job details" --json`.

## 3. Decide: personal or shared?

| | Personal | Shared (contribution) |
|---|---|---|
| Where | `local_sources/<name>.py` | `src/jobhunt/sources/<name>.py` |
| In git | No: gitignored, stays on your machine | Yes: open a PR |
| Imports | absolute: `from jobhunt.models import Job` | relative: `from ..models import Job` |
| Tests | `local_sources/test_<name>.py`, run with `uv run pytest local_sources` | `tests/test_sources.py` + a case in `tests/test_live.py` |
| Good for | A company only you follow, quick experiments, patching a broken built-in (same name overrides it) | A platform (Workday, SmartRecruiters…) or a company many people want |

Start personal. You can promote a source later by moving the file and switching the imports.

## 4. Port the client into the module

Read the generated client before using it: it's model-written code. Don't drop it in as
is. Port the endpoints into a module that follows the contract in
[`src/jobhunt/sources/__init__.py`](../src/jobhunt/sources/__init__.py):

```python
"""<Company> careers (<host>).  <- first line shows in `jobhunt sources`

Reverse-engineered with reverse-api-engineer: <which endpoints, what auth/CSRF, page size>.
Site filters (profile.yaml -> search.site_filters.<key>): <location: ..., ...>
"""
from collections.abc import Iterable
from ..models import Job
from ..util import client, html_to_text

PRESETS = {"acme": {"name": "Acme"}}        # lets `jobhunt add Acme` find this source

def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    f = company.get("site_filters") or {}   # personal filters from profile.yaml
    ...
    yield Job(company=company["key"], source="<name>", external_id=..., title=..., url=..., locations=[...])

def fetch_description(job: Job) -> str | None:   # optional, if listings lack the full text
    ...

def from_url(url: str, ctx) -> Job | None:        # optional, for `/apply <link>`
    # Return None if the URL isn't yours. Use ctx.key_for("<name>") for Job.company so an
    # imported job gets the same uid as a discovered one.
    ...

COMPLETE_LISTING = False   # True only if fetch() returns every open role (then vanished roles close)
```

Without `from_url`, `/apply <link>` still works for most sites through the page's schema.org
`JobPosting`. Add it when the site's pages don't carry that, or the ids differ from discovery.

The module is picked up automatically from its filename, from either folder. Checklist (each item caught a real
bug in the built-in sources):

- [ ] Use `jobhunt.util.client()` (httpx) and drop `requests`. Don't advertise `br` encoding.
- [ ] Decode embedded JSON with a real parser (`json.JSONDecoder().raw_decode`), never by
      counting brackets. Descriptions contain `[` and `]`.
- [ ] Decode JS string literals with `json.loads('"' + s + '"')`, not `unicode_escape`,
      which garbles non-ASCII text.
- [ ] Use `company["key"]` for `Job.company`. Never hard-code it.
- [ ] Respect `site_filters` for server-side location filters. Big sites can't be crawled whole.
      Check that a filter really filters: some silently return nothing for the wrong format.
- [ ] Cap pagination (`max_pages`) and sleep between pages.
- [ ] If the site uses rotating identifiers (GraphQL `doc_id`, build hashes), add a fallback that
      rediscovers them. See `meta.py`.
- [ ] Raise a clear `ValueError("<Company> page structure changed: …")` when the expected data
      is missing, so `discover` reports it instead of returning 0 jobs.

## 5. Test it

Add an offline fixture test that pins the parsing assumptions (`local_sources/test_<name>.py`
for a personal source, `tests/test_sources.py` for a shared one), then run it live:

```bash
uv run --extra dev pytest -q local_sources   # personal; or `pytest -q` for shared
uv run jobhunt add "<Company>"            # picks up your PRESETS entry
uv run jobhunt discover <key> && uv run jobhunt jobs --company <key>
uv run jobhunt show <uid>                 # full description present?
```

If it's a shared source, open a PR. Never commit HAR files or `rae.ndjson`: they can contain cookies.
