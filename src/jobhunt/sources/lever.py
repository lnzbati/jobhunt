"""Lever public Postings API — https://github.com/lever/postings-api"""
from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import Job
from ..util import client, html_to_text, ms_to_iso

# Returns the whole board, so roles missing from a fetch have been taken down.
COMPLETE_LISTING = True

API = "https://api.lever.co/v0/postings/{board}"
_URL = re.compile(r"jobs\.(?:eu\.)?lever\.co/([\w.-]+)/([0-9a-f]{8}-[0-9a-f-]{27})")


def _to_job(key: str, board: str, j: dict) -> Job:
    cat = j.get("categories") or {}
    locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
    parts = [j.get("descriptionPlain") or ""]
    for lst in j.get("lists") or []:
        parts += [lst.get("text", ""), lst.get("content", "")]
    parts.append(j.get("additionalPlain") or "")
    return Job(
        company=key,
        source="lever",
        external_id=j["id"],
        title=j["text"].strip(),
        url=j["hostedUrl"],
        apply_url=j.get("applyUrl"),
        locations=locs,
        team=cat.get("team") or cat.get("department"),
        remote=(j.get("workplaceType") == "remote") or None,
        posted_at=ms_to_iso(j.get("createdAt")),
        description=html_to_text("\n".join(p for p in parts if p)),
        meta={"board": board},
    )


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    board = company["board"]
    with client() as c:
        r = c.get(API.format(board=board), params={"mode": "json"})
        r.raise_for_status()
        for j in r.json():
            yield _to_job(company["key"], board, j)


def from_url(url: str, ctx) -> Job | None:
    m = _URL.search(url)
    if not m:
        return None
    board, pid = m.groups()
    with client() as c:
        r = c.get(API.format(board=board) + f"/{pid}", params={"mode": "json"})
        r.raise_for_status()
    return _to_job(ctx.key_for("lever", board=board), board, r.json())
