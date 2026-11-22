"""Greenhouse public Job Board API — https://developers.greenhouse.io/job-board.html"""
from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import parse_qs, urlparse

from ..models import Job
from ..util import client, html_to_text

# Returns the whole board, so roles missing from a fetch have been taken down.
COMPLETE_LISTING = True

API = "https://boards-api.greenhouse.io/v1/boards/{board}"
_URL = re.compile(r"greenhouse\.io/([\w-]+)/jobs/(\d+)")


def _to_job(key: str, board: str, j: dict) -> Job:
    loc = (j.get("location") or {}).get("name") or ""
    meta = {m["name"]: m.get("value") for m in j.get("metadata") or []}
    loc_type = str(meta.get("Location Type") or "")
    return Job(
        company=key,
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
        meta={"board": board},
    )


def fetch(company: dict, queries: list[str]) -> Iterable[Job]:
    board = company["board"]
    with client() as c:
        # content=true includes descriptions: one request per board instead of one per job
        r = c.get(API.format(board=board) + "/jobs", params={"content": "true"})
        r.raise_for_status()
        for j in r.json()["jobs"]:
            yield _to_job(company["key"], board, j)


def _get_job(c, board: str, job_id: str):
    return c.get(API.format(board=board) + f"/jobs/{job_id}", params={"questions": "true"})


def from_url(url: str, ctx) -> Job | None:
    """boards.greenhouse.io/<board>/jobs/<id>, or a company-hosted page with ?gh_jid=<id>
    (then the board is looked up among the configured Greenhouse companies)."""
    m = _URL.search(url)
    if m:
        candidates, job_id = [m.group(1)], m.group(2)
    else:
        qs = parse_qs(urlparse(url).query)
        job_id = (qs.get("gh_jid") or [None])[0]
        if not job_id:
            return None
        host = urlparse(url).netloc.removeprefix("www.").split(".")
        guess = host[-2] if len(host) >= 2 else None  # stripe.com/jobs?gh_jid=... -> board "stripe"
        configured = [c["board"] for c in ctx.companies if c.get("source") == "greenhouse"]
        candidates = list(dict.fromkeys([*(qs.get("for") or []), *([guess] if guess else []), *configured]))
    with client() as c:
        for board in candidates:
            r = _get_job(c, board, job_id)
            if r.status_code == 200:
                return _to_job(ctx.key_for("greenhouse", board=board), board, r.json())
    return None


def fetch_questions(job: Job) -> list[dict] | None:
    """The application form's questions, so answers can be drafted before opening the form."""
    board = job.meta.get("board")
    if not board:
        return None
    with client() as c:
        r = _get_job(c, board, job.external_id)
    if r.status_code != 200:
        return None
    out = []
    for q in r.json().get("questions") or []:
        fields = q.get("fields") or [{}]
        options = [v.get("label") for f in fields for v in f.get("values") or [] if v.get("label")]
        out.append({"label": q.get("label"), "required": bool(q.get("required")),
                    "type": fields[0].get("type"), "options": options or None,
                    "description": html_to_text(q.get("description"))})
    return out
