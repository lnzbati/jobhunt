"""Greenhouse public Job Board API — https://developers.greenhouse.io/job-board.html"""
from __future__ import annotations

from collections.abc import Iterable

from ..models import Job
from ..util import client, html_to_text

# Returns the whole board, so roles missing from a fetch have been taken down.
COMPLETE_LISTING = True

API = "https://boards-api.greenhouse.io/v1/boards/{board}"


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    board = company["board"]
    with client() as c:
        # content=true includes descriptions: one request per board instead of one per job
        r = c.get(API.format(board=board) + "/jobs", params={"content": "true"})
        r.raise_for_status()
        for j in r.json()["jobs"]:
            loc = (j.get("location") or {}).get("name") or ""
            meta = {m["name"]: m.get("value") for m in j.get("metadata") or []}
            loc_type = str(meta.get("Location Type") or "")
            yield Job(
                company=company["key"],
                source="greenhouse",
                external_id=str(j["id"]),
                title=j["title"].strip(),
                url=j["absolute_url"],
                apply_url=j["absolute_url"],
                locations=[p.strip() for p in loc.split("|") if p.strip()] or ([loc] if loc else []),
                remote=("remote" in loc.lower() or "remote" in loc_type.lower()) or None,
                posted_at=j.get("first_published") or j.get("updated_at"),
                team=", ".join(d["name"] for d in j.get("departments") or []) or None,
                description=html_to_text(j.get("content")),
            )

