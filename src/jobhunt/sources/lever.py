"""Lever public Postings API — https://github.com/lever/postings-api"""
from __future__ import annotations

from collections.abc import Iterable

from ..models import Job
from ..util import client, html_to_text, ms_to_iso

# Returns the whole board, so roles missing from a fetch have been taken down.
COMPLETE_LISTING = True

API = "https://api.lever.co/v0/postings/{board}"


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    with client() as c:
        r = c.get(API.format(board=company["board"]), params={"mode": "json"})
        r.raise_for_status()
        for j in r.json():
            cat = j.get("categories") or {}
            locs = cat.get("allLocations") or ([cat["location"]] if cat.get("location") else [])
            desc_parts = [j.get("descriptionPlain") or ""]
            for lst in j.get("lists") or []:
                desc_parts.append(lst.get("text", ""))
                desc_parts.append(lst.get("content", ""))
            desc_parts.append(j.get("additionalPlain") or "")
            yield Job(
                company=company["key"],
                source="lever",
                external_id=j["id"],
                title=j["text"].strip(),
                url=j["hostedUrl"],
                apply_url=j.get("applyUrl"),
                locations=locs,
                team=cat.get("team") or cat.get("department"),
                remote=(j.get("workplaceType") == "remote") or None,
                posted_at=ms_to_iso(j.get("createdAt")),
                description=html_to_text("\n".join(p for p in desc_parts if p)),
            )
