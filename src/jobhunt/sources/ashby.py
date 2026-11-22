"""Ashby public Job Posting API — https://developers.ashbyhq.com/docs/public-job-posting-api"""
from __future__ import annotations

from collections.abc import Iterable

from ..models import Job
from ..util import client

# Returns the whole board, so roles missing from a fetch have been taken down.
COMPLETE_LISTING = True

API = "https://api.ashbyhq.com/posting-api/job-board/{board}"


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    with client() as c:
        r = c.get(API.format(board=company["board"]), params={"includeCompensation": "true"})
        r.raise_for_status()
        for j in r.json()["jobs"]:
            if j.get("isListed") is False:
                continue
            locs = [j["location"]] if j.get("location") else []
            locs += [s.get("location") for s in j.get("secondaryLocations") or [] if s.get("location")]
            yield Job(
                company=company["key"],
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
            )
