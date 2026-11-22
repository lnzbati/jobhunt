"""Work out which source a company's careers page uses, so companies can be added on the fly.

Strategy:
  1. Parse well-known ATS URLs directly (boards.greenhouse.io/x, jobs.lever.co/x, jobs.ashbyhq.com/x).
  2. Otherwise fetch the careers page and look for embedded ATS links/iframes.
  3. Otherwise guess board slugs from the company name and probe the public APIs.
If all fail, the site is custom: capture it with reverse-api-engineer and add a source module.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from .util import client

PATTERNS = [
    ("greenhouse", re.compile(
        r"(?:boards|job-boards)(?:\.eu)?\.greenhouse\.io/(?:embed/job_board\?for=)?([A-Za-z0-9_-]+)")),
    ("greenhouse", re.compile(r"boards-api\.greenhouse\.io/v1/boards/([A-Za-z0-9_-]+)")),
    ("lever", re.compile(r"jobs\.(?:eu\.)?lever\.co/([A-Za-z0-9_.-]+)")),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([A-Za-z0-9_.%-]+)")),
]

PROBES = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
    "lever": "https://api.lever.co/v0/postings/{slug}?mode=json&limit=1",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{slug}",
}

IGNORE_SLUGS = {"embed", "api", "v1", "jobs"}


def _from_text(text: str) -> tuple[str, str] | None:
    for source, pat in PATTERNS:
        for m in pat.finditer(text):
            slug = m.group(1)
            if slug.lower() not in IGNORE_SLUGS:
                return source, slug
    return None


def _slug_candidates(name: str) -> list[str]:
    base = re.sub(r"[^a-z0-9 ]", "", name.lower()).strip()
    # Full-name variants only: a first-word guess ("scale" for "Scale AI") matches unrelated boards.
    cands = [base.replace(" ", ""), base.replace(" ", "-")]
    return list(dict.fromkeys(c for c in cands if c))


def detect(name: str, url: str | None = None) -> dict | None:
    """Return {'source': ..., 'board': ...} or None if no public ATS was found."""
    if url:
        hit = _from_text(url)
        if hit:
            return {"source": hit[0], "board": hit[1], "matched_by": "url"}
    with client(headers={"Accept": "text/html,*/*"}) as c:
        if url:
            try:
                r = c.get(url)
                hit = _from_text(str(r.url)) or _from_text(r.text)
                if hit:
                    return {"source": hit[0], "board": hit[1], "matched_by": "careers_page"}
            except httpx.HTTPError:
                pass  # unreachable careers page: fall through to probing by name
        for slug in _slug_candidates(name):
            for source, probe in PROBES.items():
                try:
                    r = c.get(probe.format(slug=slug))
                except httpx.HTTPError:
                    continue
                if r.status_code == 200 and _non_empty(source, r):
                    return {"source": source, "board": slug, "matched_by": "name_guess"}
    return None


def _non_empty(source: str, r) -> bool:
    try:
        data = r.json()
    except ValueError:
        return False
    if source == "lever":
        return isinstance(data, list) and len(data) > 0
    return bool(data.get("jobs"))


def host(url: str) -> str:
    return urlparse(url).netloc
