"""Eightfold.ai careers sites (Microsoft and others).

Reverse-engineered from apply.careers.microsoft.com with reverse-api-engineer. The
"PCSX" careers module exposes a public, unauthenticated JSON API:

  GET {base}/api/pcsx/search?domain=<group id>&query=&location=&start=&sort_by=timestamp
      -> {"status": 200, "data": {"count": N, "positions": [...]}}      (10 per page)
  GET {base}/api/pcsx/position_details?domain=<group id>&position_id=<id>
      -> {"status": 200, "data": {..., "jobDescription": "<html>"}}

companies.yaml:   source: eightfold, base_url: https://apply.careers.microsoft.com, domain: microsoft.com
Site filters (profile.yaml -> search.site_filters.<key>):
  location:  free text, e.g. "London, United Kingdom"
  filters:   {seniority: [Senior, Mid-Level], employment_type: [full-time], ...}
  max_pages: per query (default 10)
"""
from __future__ import annotations

import re
import time
from collections.abc import Iterable
from datetime import UTC, datetime

from ..models import Job
from ..util import client, html_to_text

PRESETS = {
    "microsoft": {"name": "Microsoft", "base_url": "https://apply.careers.microsoft.com", "domain": "microsoft.com"},
}

PAGE_SIZE = 10


def _get(c, url: str, params) -> dict:
    for attempt in range(4):
        r = c.get(url, params=params)
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        body = r.json()
        if body.get("status") != 200:
            raise RuntimeError(f"Eightfold API error: {body.get('error') or body}")
        return body["data"]
    r.raise_for_status()
    raise RuntimeError("Eightfold API kept rate-limiting")


def _iso(ts) -> str | None:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat() if ts else None


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    base, domain = company["base_url"].rstrip("/"), company["domain"]
    f = company.get("site_filters") or {}
    max_pages = int(f.get("max_pages", 10))
    seen: set[str] = set()
    with client(headers={"Referer": f"{base}/careers"}) as c:
        for q in queries or [""]:
            for page in range(max_pages):
                params = [("domain", domain), ("query", q), ("location", f.get("location", "")),
                          ("start", page * PAGE_SIZE), ("sort_by", "timestamp")]
                for name, values in (f.get("filters") or {}).items():
                    params += [(f"filter_{name}", v) for v in values]
                data = _get(c, f"{base}/api/pcsx/search", params)
                positions = data.get("positions") or []
                for p in positions:
                    pid = str(p["id"])
                    if pid in seen:
                        continue
                    seen.add(pid)
                    yield Job(
                        company=company["key"],
                        source="eightfold",
                        external_id=pid,
                        title=p["name"].strip(),
                        url=f"{base}{p['positionUrl']}" if p.get("positionUrl") else f"{base}/careers/job/{pid}",
                        locations=p.get("standardizedLocations") or p.get("locations") or [],
                        team=p.get("department"),
                        remote=(p.get("workLocationOption") == "remote") or None,
                        posted_at=_iso(p.get("postedTs")),
                    )
                if len(positions) < PAGE_SIZE or (page + 1) * PAGE_SIZE >= (data.get("count") or 0):
                    break
                time.sleep(0.5)


def _details(c, base: str, domain: str, pid: str) -> dict:
    return _get(c, f"{base}/api/pcsx/position_details", {"domain": domain, "position_id": pid})


def fetch_description(job: Job) -> str | None:
    base = job.url.split("/careers/")[0]
    from ..config import load_companies
    domain = next((c["domain"] for c in load_companies() if c["key"] == job.company), None)
    if not domain:
        return None
    with client(headers={"Referer": f"{base}/careers"}) as c:
        d = _details(c, base, domain, job.external_id)
    return html_to_text(d.get("jobDescription"))


_URL = re.compile(r"(https://[^/]+)/careers/job/(\d+)")


def from_url(url: str, ctx) -> Job | None:
    m = _URL.search(url)
    if not m:
        return None
    base, pid = m.groups()
    sites = [c for c in ctx.companies if c.get("source") == "eightfold"] + \
        [{"key": k, **p} for k, p in PRESETS.items()]
    site = next((s for s in sites if s.get("base_url", "").rstrip("/") == base), None)
    if not site:
        return None  # an Eightfold site we don't know the domain for: let JSON-LD handle it
    with client(headers={"Referer": f"{base}/careers"}) as c:
        p = _details(c, base, site["domain"], pid)
    return Job(
        company=ctx.key_for("eightfold", name=site.get("name")),
        source="eightfold",
        external_id=str(p.get("id") or pid),
        title=(p.get("name") or "").strip(),
        url=f"{base}/careers/job/{pid}",
        locations=p.get("standardizedLocations") or p.get("locations") or [],
        team=p.get("department"),
        remote=(p.get("workLocationOption") == "remote") or None,
        posted_at=_iso(p.get("postedTs")),
        description=html_to_text(p.get("jobDescription")),
    )
