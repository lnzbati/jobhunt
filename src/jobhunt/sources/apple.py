"""Apple careers (jobs.apple.com).

Reverse-engineered with reverse-api-engineer: the search page is server-rendered and embeds
its results as `window.__staticRouterHydrationData = JSON.parse("...")`. No auth or CSRF is
needed for reading. 20 results per page.

Site filters (profile.yaml -> search.site_filters.apple):
  location: location slug, e.g. united-kingdom-GBR, united-states-USA, germany-DEU
  team:     team code, e.g. SFTWR, MLAI, HRDWR
  max_pages: per query (default 10)
"""
from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Iterable

from ..models import Job
from ..util import client, html_to_text

PRESETS = {"apple": {"name": "Apple"}}

BASE = "https://jobs.apple.com"
LOCALE = "en-gb"
PAGE_SIZE = 20
_HYDRATION = re.compile(r'window\.__staticRouterHydrationData\s*=\s*JSON\.parse\("(.*?)"\);\s*</script>', re.S)


def _hydration(html: str) -> dict:
    m = _HYDRATION.search(html)
    if not m:
        raise ValueError("Apple page structure changed: __staticRouterHydrationData not found")
    # The payload is a JS string literal containing JSON: decode the literal, then the JSON.
    return json.loads(json.loads(f'"{m.group(1)}"'))


def _search(c, query: str, location: str | None, team: str | None, page: int) -> dict:
    params = {"search": query, "sort": "newest"}
    if location:
        params["location"] = location
    if team:
        params["team"] = team
    if page > 1:
        params["page"] = page
    r = c.get(f"{BASE}/{LOCALE}/search", params=params)
    r.raise_for_status()
    return _hydration(r.text)["loaderData"]["search"]


def _to_job(company_key: str, raw: dict) -> Job:
    pid = raw["positionId"]
    locs = [loc.get("name") or ", ".join(x for x in (loc.get("city"), loc.get("countryName")) if x)
            for loc in raw.get("locations") or []]
    return Job(
        company=company_key,
        source="apple",
        external_id=str(pid),
        title=raw.get("postingTitle", "").strip(),
        url=f"{BASE}/{LOCALE}/details/{pid}/{raw.get('transformedPostingTitle', '')}",
        apply_url=None,  # the details page has the Apply button (requires an Apple Account)
        locations=[loc for loc in locs if loc],
        team=(raw.get("team") or {}).get("teamName"),
        remote=bool(raw.get("homeOffice")) or None,
        posted_at=raw.get("postDateInGMT") or raw.get("postingDate"),
        description=None,  # listing only has a teaser; full text via fetch_description()
    )


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    f = company.get("site_filters") or {}
    max_pages = int(f.get("max_pages", 10))
    seen: set[str] = set()
    with client(headers={"Accept": "text/html,*/*"}) as c:
        for q in queries or [""]:
            page = 1
            while True:
                s = _search(c, q, f.get("location"), f.get("team"), page)
                for raw in s.get("searchResults") or []:
                    job = _to_job(company["key"], raw)
                    if job.external_id not in seen:
                        seen.add(job.external_id)
                        yield job
                total_pages = math.ceil((s.get("totalRecords") or 0) / PAGE_SIZE)
                if page >= min(total_pages, max_pages) or not s.get("searchResults"):
                    break
                page += 1
                time.sleep(0.5)


def _details(position_id: str) -> dict | None:
    with client(headers={"Accept": "text/html,*/*"}) as c:
        r = c.get(f"{BASE}/{LOCALE}/details/{position_id}/x")
    if r.status_code != 200:
        return None
    return _hydration(r.text)["loaderData"]["jobDetails"]["jobsData"]


def _description(d: dict) -> str | None:
    sections = [
        ("Summary", d.get("jobSummary")),
        ("Description", d.get("description")),
        ("Responsibilities", d.get("responsibilities")),
        ("Minimum qualifications", d.get("minimumQualifications")),
        ("Preferred qualifications", d.get("preferredQualifications")),
    ]
    return "\n\n".join(f"## {h}\n{html_to_text(t)}" for h, t in sections if t) or None


def fetch_description(job: Job) -> str | None:
    d = _details(job.external_id)
    return _description(d) if d else None


_URL = re.compile(r"jobs\.apple\.com/[^?#]*details/(\d+)")


def from_url(url: str, ctx) -> Job | None:
    m = _URL.search(url)
    if not m:
        return None
    d = _details(m.group(1))
    if not d:
        raise LookupError(f"Apple posting {m.group(1)} not found (closed?)")
    job = _to_job(ctx.key_for("apple"), {**d, "positionId": d.get("positionId") or m.group(1)})
    job.description = _description(d)
    return job
