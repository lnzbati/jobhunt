"""Meta careers (metacareers.com).

Reverse-engineered with reverse-api-engineer. The site is a Relay SPA:

  1. GET  /jobs          -> HTML containing the LSD (CSRF) token: "LSD",[],{"token":"..."}
  2. POST /graphql       form-encoded, doc_id = persisted CareersJobSearchResultsDataQuery,
                         X-FB-LSD header + lsd field. Returns *all* matches in one response.

Persisted-query doc_ids change when Meta ships new JS bundles. DOC_ID is the last known value.
If it stops working, the adapter scans the JS bundles referenced by the page (about 1,200,
escaped inside its JSON) for
`__d("CareersJobSearchResultsDataQuery_<app>RelayOperation",[],(function(...){a.exports="<doc_id>"})`.

Each query returns every match in one response (hundreds, not tens of thousands), so
location filtering is left to the profile prefilter. The server-side `offices` filter
expects internal values rather than display names and silently returns nothing otherwise.

Site filters (profile.yaml -> search.site_filters.meta), all optional:
  teams:   ["Software Engineering", "AI Research"]
  remote_only: false
"""
from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

import httpx

from ..models import Job
from ..util import client, html_to_text

PRESETS = {"meta": {"name": "Meta"}}

BASE = "https://www.metacareers.com"
DOC_ID = "40084319704492118"  # CareersJobSearchResultsDataQuery, Nov 2026
OPERATION = "CareersJobSearchResultsDataQuery"
_LSD = re.compile(r'"LSD",\[\],\{"token":"([^"]+)"')
_BUNDLE = re.compile(r'https://static\.xx\.fbcdn\.net/rsrc\.php/[^"\\\s]+?\.js[^"\\\s]*')
_OP = re.compile(r'__d\("' + OPERATION + r'_\w*RelayOperation",\[\],\(function\([^)]*\)\{\w+\.exports="(\d+)"')

_doc_id_cache: str | None = None


def _browser():
    # Without the Sec-Fetch-* navigation headers Meta serves a page with no LSD token.
    return client(headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                           "Accept-Language": "en-GB,en;q=0.9", "Sec-Fetch-Mode": "navigate",
                           "Sec-Fetch-Dest": "document", "Sec-Fetch-Site": "none"})


def _discover_doc_id(c, html: str) -> str | None:
    """Slow path (a few hundred requests): only used when the known doc_id is rejected."""
    m = _OP.search(html)
    if m:
        return m.group(1)
    # /jobs sometimes serves a light page; /jobsearch/ lists the full set of lazy bundles.
    with contextlib.suppress(httpx.HTTPError):
        html += c.get(f"{BASE}/jobsearch/").text
    bundles = list(dict.fromkeys(_BUNDLE.findall(html.replace("\\/", "/"))))

    def scan(url: str) -> str | None:
        try:
            hit = _OP.search(c.get(url).text)
            return hit.group(1) if hit else None
        except httpx.HTTPError:
            return None

    with ThreadPoolExecutor(max_workers=16) as ex:
        for found in ex.map(scan, bundles):
            if found:
                return found
    return None


def _query(c, lsd: str, doc_id: str, variables: dict) -> dict:
    r = c.post(
        f"{BASE}/graphql",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Origin": BASE,
                 "Referer": f"{BASE}/jobs", "X-FB-LSD": lsd, "X-FB-Friendly-Name": OPERATION},
        data={"variables": json.dumps(variables), "doc_id": doc_id, "lsd": lsd,
              "fb_api_caller_class": "RelayModern", "fb_api_req_friendly_name": OPERATION,
              "server_timestamps": "true"},
    )
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    body = json.loads(r.text.removeprefix("for (;;);"))
    data = (body.get("data") or {}).get("job_search_with_featured_jobs_v2")
    if data is None:
        raise RuntimeError(f"GraphQL error: {(body.get('errors') or [{}])[0].get('message', body)}")
    return data


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    global _doc_id_cache
    f = company.get("site_filters") or {}
    seen: set[str] = set()
    with _browser() as c:
        html = c.get(f"{BASE}/jobs").text
        m = _LSD.search(html)
        if not m:
            raise ValueError("Meta page structure changed: LSD token not found")
        lsd = m.group(1)
        doc_id = _doc_id_cache or DOC_ID

        for q in queries or [""]:
            variables = {
                "search_input": {
                    "q": q, "divisions": [], "offices": [], "roles": [], "leadership_levels": [],
                    "saved_jobs": [], "saved_searches": [], "sub_teams": [], "teams": f.get("teams") or [],
                    "is_leadership": False, "is_remote_only": bool(f.get("remote_only")),
                    "sort_by_new": True, "page": 1,
                },
                "isLoggedIn": False,
            }
            try:
                data = _query(c, lsd, doc_id, variables)
            except RuntimeError:
                fresh = _discover_doc_id(c, html)
                if not fresh or fresh == doc_id:
                    raise
                doc_id = _doc_id_cache = fresh
                data = _query(c, lsd, doc_id, variables)

            for j in data.get("all_jobs") or []:
                jid = str(j["id"])
                if jid in seen:
                    continue
                seen.add(jid)
                locs = j.get("locations") or []
                yield Job(
                    company=company["key"],
                    source="meta",
                    external_id=jid,
                    title=(j.get("title") or "").strip(),
                    url=f"{BASE}/jobs/{jid}/",
                    locations=locs,
                    team=", ".join(j.get("teams") or []) or None,
                    remote=any("remote" in loc.lower() for loc in locs) or None,
                )


def fetch_description(job: Job) -> str | None:
    """The job page is server-rendered for SEO and carries a schema.org JobPosting."""
    with _browser() as c:
        r = c.get(job.url)
    for m in re.finditer(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', r.text, re.S):
        try:
            ld = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(ld, dict) and ld.get("@type") == "JobPosting":
            parts = [ld.get("description")]
            for k in ("responsibilities", "qualifications", "experienceRequirements"):
                v = ld.get(k)
                if isinstance(v, list):
                    v = "\n".join(f"- {x}" for x in v)
                if v:
                    parts.append(f"## {k.capitalize()}\n{v}")
            return html_to_text("\n\n".join(p for p in parts if p))
    return None
