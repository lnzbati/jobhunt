"""Cheap, deterministic prefilter so Claude only has to judge plausible roles.

Configured under `search:` in profile.yaml. Matching is case-insensitive substring.
"""
from __future__ import annotations

import re

from .models import Job


def _any(needles: list[str], hay: str) -> bool:
    hay = hay.lower()
    return any(re.search(r"\b" + re.escape(n.lower()) + r"\b", hay) for n in needles)


def matches(job: Job, search: dict) -> bool:
    title = job.title
    include = search.get("title_include") or []
    exclude = search.get("title_exclude") or []
    if include and not _any(include, title):
        return False
    if exclude and _any(exclude, title):
        return False

    locs = search.get("locations") or []
    if not locs or not job.locations:
        return True
    joined = " | ".join(job.locations)
    if _any(locs, joined):
        return True
    # "Remote" is usually scoped to a region (e.g. remote-US), so a remote flag alone
    # isn't enough: the location text must name a region you can work from.
    if job.remote and search.get("remote_ok", True):
        return _any(search.get("remote_regions") or [], joined)
    return False
