"""Ashby public Job Posting API — https://developers.ashbyhq.com/docs/public-job-posting-api"""
from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import Job
from ..util import client

# Returns the whole board, so roles missing from a fetch have been taken down.
COMPLETE_LISTING = True

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"
_URL = re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f]{8}-[0-9a-f-]{27})")


def _board(c, board: str) -> list[dict]:
    r = c.get(API.format(board=board), params={"includeCompensation": "true"})
    r.raise_for_status()
    return r.json()["jobs"]


def _to_job(key: str, board: str, j: dict) -> Job:
    locs = [j["location"]] if j.get("location") else []
    locs += [s.get("location") for s in j.get("secondaryLocations") or [] if s.get("location")]
    return Job(
        company=key,
        source="ashby",
        external_id=j["id"],
        title=j["title"].strip(),
        url=j["jobUrl"],
        apply_url=j.get("applyUrl"),
        locations=locs,
        team=j.get("team") or j.get("department"),
        # isRemote is also true for Hybrid roles; workplaceType is authoritative when present
        remote=(j["workplaceType"] == "Remote") if j.get("workplaceType") else bool(j.get("isRemote")),
        posted_at=j.get("publishedAt"),
        description=j.get("descriptionPlain"),
        meta={"board": board},
    )


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    board = company["board"]
    with client() as c:
        for j in _board(c, board):
            if j.get("isListed") is not False:
                yield _to_job(company["key"], board, j)


def from_url(url: str, ctx) -> Job | None:
    m = _URL.search(url)
    if not m:
        return None
    board, pid = m.groups()
    with client() as c:
        found = next((j for j in _board(c, board) if j["id"] == pid), None)
    if not found:
        raise LookupError(f"Ashby posting {pid} is not on the {board} board (closed?)")
    return _to_job(ctx.key_for("ashby", board=board), board, found)
