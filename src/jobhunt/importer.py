"""Turn a single job-posting link into a stored Job (for `/apply <link>`).

Resolution order:
  1. Source modules that recognise the URL (`from_url(url, ctx)`): Greenhouse, Lever, Ashby,
     Apple, Google. These use the same APIs as discovery and give the cleanest data.
  2. The page's schema.org JobPosting (JSON-LD). Most career sites publish it for search
     engines: Microsoft, Meta, Workday, SmartRecruiters, Personio, many bespoke sites.
  3. Fallback: page title + visible text, flagged `needs_review` so the skill reads the real
     posting in the browser before tailoring anything.
"""
from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import urlparse

from . import config, sources
from .models import Job
from .util import client, html_to_text

_LD = re.compile(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL | re.IGNORECASE)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())[:40] or "company"


class ImportContext:
    """What a source needs to place a single job: the configured companies and a key mapper."""

    def __init__(self, companies: list[dict]):
        self.companies = companies

    def key_for(self, source: str, board: str | None = None, name: str | None = None) -> str:
        """Use the configured company's key when there is one, so an imported job lines up with
        discovered ones (same uid, no duplicates); otherwise derive a stable key."""
        for c in self.companies:
            if c.get("source") == source and (board is None or c.get("board") == board):
                return c["key"]
        if name:
            for c in self.companies:
                if c.get("name", "").lower() == name.lower():
                    return c["key"]
        preset = next((k for k, p in sources.presets().items() if p["source"] == source), None)
        return board or preset or (_slug(name) if name else source)


def _companies() -> list[dict]:
    try:
        return config.load_companies(include_disabled=True)
    except config.ConfigError:
        return []  # importing a single link must work before any company is configured


def _job_postings(html: str) -> list[dict]:
    found = []
    for m in _LD.finditer(html):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                t = x.get("@type")
                if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                    found.append(x)
                stack.extend(x.get("@graph") or [])
    return found


def _ld_locations(p: dict) -> list[str]:
    locs = p.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    out = []
    for loc in locs:
        addr = (loc or {}).get("address") or {}
        if isinstance(addr, str):
            out.append(addr)
            continue
        parts = [addr.get("addressLocality"), addr.get("addressRegion"), _country(addr.get("addressCountry"))]
        text = ", ".join(dict.fromkeys(x for x in parts if x))
        if text:
            out.append(text)
    if str(p.get("jobLocationType", "")).upper() == "TELECOMMUTE":
        out.append("Remote")
    return out


def _country(c) -> str | None:
    return c.get("name") if isinstance(c, dict) else c


def _from_json_ld(url: str, html: str, ctx: ImportContext) -> Job | None:
    postings = _job_postings(html)
    if not postings:
        return None
    p = postings[0]
    org = p.get("hiringOrganization") or {}
    org_name = org.get("name") if isinstance(org, dict) else str(org)
    ident = p.get("identifier")
    ident = ident.get("value") if isinstance(ident, dict) else ident
    parts = [p.get("description")]
    for k in ("responsibilities", "qualifications", "skills", "experienceRequirements"):
        v = p.get(k)
        if isinstance(v, list):
            v = "\n".join(f"- {x}" for x in v)
        if isinstance(v, str) and v.strip():
            parts.append(f"## {k.capitalize()}\n{v}")
    return Job(
        company=ctx.key_for("link", name=org_name or urlparse(url).netloc),
        source="link",
        external_id=str(ident or _url_id(url)),
        title=(p.get("title") or "").strip() or "Untitled role",
        url=url,
        apply_url=p.get("url") or url,
        locations=_ld_locations(p),
        remote=(str(p.get("jobLocationType", "")).upper() == "TELECOMMUTE") or None,
        posted_at=p.get("datePosted"),
        description=html_to_text("\n\n".join(x for x in parts if x)),
        meta={"company_name": org_name, "imported_via": "json-ld"},
    )


def _url_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def _fallback(url: str, html: str, ctx: ImportContext) -> Job:
    m = _TITLE.search(html)
    title = html_to_text(m.group(1)) if m else "Untitled role"
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    host = urlparse(url).netloc.removeprefix("www.")
    return Job(
        company=ctx.key_for("link", name=host.split(".")[-2] if host.count(".") else host),
        source="link",
        external_id=_url_id(url),
        title=title.strip()[:200],
        url=url,
        apply_url=url,
        description=(html_to_text(body) or "")[:20000] or None,
        meta={"imported_via": "page-text", "needs_review": True},
    )


def import_url(url: str) -> Job:
    ctx = ImportContext(_companies())
    for name, mod in sources.available().items():
        fn = getattr(mod, "from_url", None)
        if fn:
            job = fn(url, ctx)
            if job:
                job.meta.setdefault("imported_via", name)
                return job
    headers = {"Accept": "text/html,application/xhtml+xml,*/*;q=0.8", "Accept-Language": "en-GB,en;q=0.9",
               "Sec-Fetch-Mode": "navigate", "Sec-Fetch-Dest": "document", "Sec-Fetch-Site": "none"}
    with client(headers=headers) as c:
        r = c.get(url)
        r.raise_for_status()
    return _from_json_ld(str(r.url), r.text, ctx) or _fallback(str(r.url), r.text, ctx)
