"""Google careers (incl. DeepMind, YouTube, Wing).

Reverse-engineered with reverse-api-engineer: the results page is server-rendered and
embeds its data as `AF_initDataCallback({key: 'ds:1', ..., data: [[jobs], null, total, per_page]})`.
No auth needed. 20 results per page; `page` is 1-indexed.

Job array layout (positional, may change):
  0 id · 1 title · 2 apply URL · 3 [_, responsibilities html] · 4 [_, qualifications html]
  7 company · 9 [[display location, ...], ...] · 10 [_, about html] · 12 created [secs, nanos]

Site filters (profile.yaml -> search.site_filters.google):
  location:  e.g. "London, UK" (repeatable as a list)
  company:   Google | DeepMind | YouTube | Wing (omit for all)
  max_pages: per query (default 10)
"""
from __future__ import annotations

import json
import math
import re
import time
from collections.abc import Iterable

from ..models import Job
from ..util import client, html_to_text, ms_to_iso

PRESETS = {
    "google": {"name": "Google"},
    "deepmind": {"name": "Google DeepMind", "site_filters": {"company": "DeepMind"}},
}

BASE = "https://www.google.com/about/careers/applications/jobs/results/"
_DS1 = re.compile(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:", re.S)


def _parse(html: str) -> tuple[list, int, int]:
    m = _DS1.search(html)
    if not m:
        raise ValueError("Google page structure changed: AF_initDataCallback ds:1 not found")
    data, _ = json.JSONDecoder().raw_decode(html[m.end():].lstrip())
    return data[0] or [], data[2] or 0, data[3] or 20


def _html(field) -> str | None:
    return html_to_text(field[1]) if isinstance(field, list) and len(field) > 1 and field[1] else None


def _slug(title: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"\s+", "-", re.sub(r"[^a-z0-9\s-]", "", title.lower()).strip()))


def _to_job(company_key: str, r: list) -> Job:
    sections = [("About the job", _html(r[10]) if len(r) > 10 else None),
                ("Responsibilities", _html(r[3])),
                ("Qualifications", _html(r[4]))]
    created = r[12][0] if len(r) > 12 and isinstance(r[12], list) and r[12] else None
    return Job(
        company=company_key,
        source="google",
        external_id=str(r[0]),
        title=r[1].strip(),
        url=f"{BASE}{r[0]}-{_slug(r[1])}",
        apply_url=r[2] if isinstance(r[2], str) else None,
        locations=[loc[0] for loc in (r[9] or []) if isinstance(loc, list) and loc and isinstance(loc[0], str)],
        team=r[7] if isinstance(r[7], str) else None,  # Google / DeepMind / YouTube / Wing
        posted_at=ms_to_iso(created * 1000) if created else None,
        description="\n\n".join(f"## {h}\n{t}" for h, t in sections if t) or None,
    )


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    f = company.get("site_filters") or {}
    locations = f.get("location") or []
    locations = [locations] if isinstance(locations, str) else locations
    max_pages = int(f.get("max_pages", 10))
    seen: set[str] = set()
    with client(headers={"Accept": "text/html,*/*", "Accept-Language": "en-GB,en;q=0.9"}) as c:
        for q in queries or [""]:
            page = 1
            while True:
                params = [("q", q), ("page", page)] + [("location", loc) for loc in locations]
                if f.get("company"):
                    params.append(("company", f["company"]))
                r = c.get(BASE, params=params)
                r.raise_for_status()
                rows, total, per = _parse(r.text)
                for row in rows:
                    job = _to_job(company["key"], row)
                    if job.external_id not in seen:
                        seen.add(job.external_id)
                        yield job
                if not rows or page >= min(math.ceil(total / per), max_pages):
                    break
                page += 1
                time.sleep(0.5)
