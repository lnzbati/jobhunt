"""SQLite store: every job ever seen, and where it is in the pipeline.

Statuses: new -> shortlisted -> drafted -> ready -> applied
          (or skipped / closed at any point)
"""
from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime

from .config import DATA_DIR
from .models import Job

STATUSES = ("new", "shortlisted", "drafted", "ready", "applied", "skipped", "closed")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    uid         TEXT PRIMARY KEY,
    company     TEXT NOT NULL,
    source      TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    apply_url   TEXT,
    locations   TEXT,          -- JSON list
    team        TEXT,
    remote      INTEGER,
    posted_at   TEXT,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'new',
    score       REAL,
    notes       TEXT,
    meta        TEXT,          -- JSON dict of source-specific extras
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    status_at   TEXT
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS jobs_company ON jobs(company);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DATA_DIR / "jobs.db")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    cols = {r["name"] for r in db.execute("PRAGMA table_info(jobs)")}
    if "meta" not in cols:  # databases created before the meta column existed
        db.execute("ALTER TABLE jobs ADD COLUMN meta TEXT")
    return db


def upsert(db: sqlite3.Connection, jobs: Iterable[Job]) -> tuple[int, int]:
    """Insert new jobs, refresh existing ones. Returns (new, updated)."""
    now, new, updated = _now(), 0, 0
    for j in jobs:
        row = db.execute("SELECT status, description FROM jobs WHERE uid=?", (j.uid,)).fetchone()
        if row is None:
            db.execute(
                """INSERT INTO jobs (uid, company, source, external_id, title, url, apply_url, locations,
                   team, remote, posted_at, description, meta, first_seen, last_seen)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (j.uid, j.company, j.source, j.external_id, j.title, j.url, j.apply_url,
                 json.dumps(j.locations), j.team, j.remote, j.posted_at, j.description,
                 json.dumps(j.meta), now, now),
            )
            new += 1
        else:
            db.execute(
                """UPDATE jobs SET title=?, url=?, apply_url=?, locations=?, team=?, remote=?, posted_at=?,
                   description=COALESCE(?, description), meta=?, last_seen=?,
                   status=CASE WHEN status='closed' THEN 'new' ELSE status END
                   WHERE uid=?""",
                (j.title, j.url, j.apply_url, json.dumps(j.locations), j.team, j.remote, j.posted_at,
                 j.description, json.dumps(j.meta), now, j.uid),
            )
            updated += 1
    db.commit()
    return new, updated


def mark_closed(db: sqlite3.Connection, company: str, seen_uids: set[str]) -> int:
    """Roles that vanished from a full board refresh are closed (unless already applied/skipped)."""
    rows = db.execute(
        "SELECT uid FROM jobs WHERE company=? AND status IN ('new','shortlisted')", (company,)
    ).fetchall()
    gone = [r["uid"] for r in rows if r["uid"] not in seen_uids]
    db.executemany("UPDATE jobs SET status='closed', status_at=? WHERE uid=?", [(_now(), u) for u in gone])
    db.commit()
    return len(gone)


def reopen_listed(db: sqlite3.Connection, company: str, listed_uids: set[str]) -> int:
    """Closed roles that are still listed on the board are open again, even if the profile
    filter no longer keeps them (filters change; a role's existence doesn't)."""
    rows = db.execute("SELECT uid FROM jobs WHERE company=? AND status='closed'", (company,)).fetchall()
    back = [r["uid"] for r in rows if r["uid"] in listed_uids]
    db.executemany("UPDATE jobs SET status='new', status_at=? WHERE uid=?", [(_now(), u) for u in back])
    db.commit()
    return len(back)


def set_status(db: sqlite3.Connection, uid: str, status: str, notes: str | None = None, score: float | None = None):
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    cur = db.execute(
        "UPDATE jobs SET status=?, status_at=?, notes=COALESCE(?, notes), score=COALESCE(?, score) WHERE uid=?",
        (status, _now(), notes, score, uid),
    )
    db.commit()
    if cur.rowcount == 0:
        raise KeyError(uid)


def get(db: sqlite3.Connection, uid: str) -> dict | None:
    r = db.execute("SELECT * FROM jobs WHERE uid=?", (uid,)).fetchone()
    return _row(r) if r else None


def query(db: sqlite3.Connection, status: str | None = None, company: str | None = None,
          since: str | None = None, limit: int | None = None) -> list[dict]:
    sql, args = "SELECT * FROM jobs WHERE 1=1", []
    if status:
        sql += " AND status=?"
        args.append(status)
    if company:
        sql += " AND company=?"
        args.append(company)
    if since:
        sql += " AND first_seen>=?"
        args.append(since)
    sql += " ORDER BY COALESCE(score, -1) DESC, first_seen DESC"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [_row(r) for r in db.execute(sql, args)]


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["locations"] = json.loads(d["locations"] or "[]")
    d["meta"] = json.loads(d.get("meta") or "{}")
    return d
