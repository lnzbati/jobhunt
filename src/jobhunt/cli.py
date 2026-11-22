"""jobhunt CLI — the deterministic half of the /job-hunt skill.

Every command prints JSON with --json so Claude can drive it reliably.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from . import config, sources, store
from .detect import detect
from .filters import matches
from .models import Job
from .sources import get_source


def _out(obj, as_json: bool, human=None):
    if as_json or human is None:
        print(json.dumps(obj, indent=2, default=str))
    else:
        human(obj)


def _fetch_company(company: dict, search: dict) -> tuple[dict, list[Job], str | None]:
    try:
        src = get_source(company["source"])
        q = company.get("queries") or search.get("queries") or []
        # personal, per-site server-side filters (e.g. Apple location slug) live in the profile
        site = (search.get("site_filters") or {}).get(company["key"])
        if site:
            company = {**company, "site_filters": {**company.get("site_filters", {}), **site}}
        return company, list(src.fetch(company, q)), None
    except Exception as e:  # noqa: BLE001 - one broken source must not sink the run
        return company, [], f"{type(e).__name__}: {e}"


def cmd_discover(a):
    profile = config.load_profile()
    search = profile.get("search") or {}
    companies = config.load_companies()
    if a.company:
        wanted = {c.lower() for c in a.company}
        companies = [c for c in companies if c["key"] in wanted]
        missing = wanted - {c["key"] for c in companies}
        if missing:
            sys.exit(f"Unknown companies: {', '.join(sorted(missing))}. Add them with `jobhunt add`.")

    db = store.connect()
    report = []
    with ThreadPoolExecutor(max_workers=6) as ex:
        for company, jobs, err in ex.map(lambda c: _fetch_company(c, search), companies):
            entry = {"company": company["key"], "fetched": len(jobs), "error": err}
            if not err:
                kept = jobs if a.no_filter else [j for j in jobs if matches(j, search)]
                new, updated = store.upsert(db, kept)
                complete = getattr(get_source(company["source"]), "COMPLETE_LISTING", False)
                closed = store.mark_closed(db, company["key"], {j.uid for j in kept}) if jobs and complete else 0
                entry.update(matched=len(kept), new=new, updated=updated, closed=closed)
            report.append(entry)

    def human(rows):
        for r in rows:
            if r["error"]:
                print(f"  {r['company']:<12} ERROR {r['error']}")
            else:
                print(f"  {r['company']:<12} fetched {r['fetched']:>5}  matched {r['matched']:>4}  "
                      f"new {r['new']:>4}  closed {r['closed']:>3}")
    _out(report, a.json, human)


def cmd_jobs(a):
    db = store.connect()
    status = None if a.status == "all" else a.status
    rows = store.query(db, status=status, company=a.company, since=a.since, limit=a.limit)
    if not a.full:
        for r in rows:
            r.pop("description", None)

    def human(rows):
        for r in rows:
            score = f"{r['score']:.0f}" if r["score"] is not None else " -"
            print(f"[{score:>3}] {r['uid']:<40} {r['title'][:60]:<60} {', '.join(r['locations'])[:40]}")
        print(f"{len(rows)} jobs")
    _out(rows, a.json, human)


def _ensure_description(db, job: dict) -> dict:
    if job.get("description"):
        return job
    src = get_source(job["source"])
    fn = getattr(src, "fetch_description", None)
    if fn:
        j = Job(**{k: job[k] for k in Job.__dataclass_fields__ if k in job})
        desc = fn(j)
        if desc:
            db.execute("UPDATE jobs SET description=? WHERE uid=?", (desc, job["uid"]))
            db.commit()
            job["description"] = desc
    return job


def cmd_show(a):
    db = store.connect()
    job = store.get(db, a.uid)
    if not job:
        sys.exit(f"No job {a.uid}")
    job = _ensure_description(db, job)

    def human(j):
        print(f"{j['title']} — {j['company']}\n{', '.join(j['locations'])}\n{j['url']}\n")
        print(j.get("description") or "(no description available — open the URL)")
    _out(job, a.json, human)


def cmd_status(a):
    db = store.connect()
    for uid in a.uid:
        store.set_status(db, uid, a.status, notes=a.notes, score=a.score)
    print(json.dumps({"updated": a.uid, "status": a.status}))


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def cmd_prepare(a):
    """Create an application folder with the job description, ready for tailoring."""
    db = store.connect()
    job = store.get(db, a.uid)
    if not job:
        sys.exit(f"No job {a.uid}")
    job = _ensure_description(db, job)
    d = config.APPS_DIR / f"{date.today().isoformat()}-{job['company']}-{_slug(job['title'])}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "job.json").write_text(json.dumps(job, indent=2, default=str))
    (d / "jd.md").write_text(
        f"# {job['title']} — {job['company']}\n\n"
        f"- Locations: {', '.join(job['locations'])}\n- Team: {job.get('team') or '-'}\n"
        f"- URL: {job['url']}\n- Apply: {job.get('apply_url') or job['url']}\n\n"
        f"{job.get('description') or '(description not available via API — read it from the URL)'}\n"
    )
    print(json.dumps({"dir": str(d), "uid": job["uid"]}))


def cmd_render(a):
    from .render import render_dir
    print(json.dumps(render_dir(a.dir), indent=2))


def cmd_add(a):
    key = a.key or _slug(a.name).replace("-", "")
    if a.source:
        cfg = {"name": a.name, "source": a.source}
        if a.board:
            cfg["board"] = a.board
        how = "explicit"
    else:
        presets = sources.presets()
        presets_by_name = {p["name"].lower(): k for k, p in presets.items()}
        preset_key = key if key in presets else presets_by_name.get(a.name.lower())
        if preset_key:  # built-in custom source (Apple, Google, Meta, Microsoft, ...)
            key = a.key or preset_key
            cfg, how = dict(presets[preset_key]), "preset"
        else:
            found = detect(a.name, a.url)
            if not found:
                print(json.dumps({
                    "added": False, "key": key,
                    "reason": "No built-in source and no public Greenhouse/Lever/Ashby board found. This is "
                              "probably a custom careers site: build a source for it with reverse-api-engineer "
                              "(docs/adding-a-source.md), then re-run `jobhunt add` with --source.",
                }, indent=2))
                sys.exit(1)
            how = found.pop("matched_by")
            cfg = {"name": a.name, **found}
    if a.url:
        cfg["careers_url"] = a.url
    p = config.save_company(key, cfg)
    out = {"added": True, "key": key, "how": how, **cfg, "saved_to": str(p)}
    if how == "name_guess":
        out["check"] = (f"Board '{cfg['board']}' was guessed from the name. Confirm it's the right company, "
                        "or pass --url <careers page> / --board <slug>.")
    print(json.dumps(out, indent=2))


def cmd_remove(a):
    for key in a.key:
        ok = config.remove_company(key)
        print(json.dumps({"removed": ok, "key": key}))


def cmd_companies(a):
    rows = [{k: c.get(k) for k in ("key", "name", "source", "board", "enabled")}
            for c in config.load_companies(include_disabled=True)]

    def human(rows):
        for r in rows:
            off = "" if r.get("enabled", True) is not False else "  (disabled)"
            print(f"  {r['key']:<12} {r['source']:<11} {r.get('board') or ''}{off}")
    _out(rows, a.json, human)


def cmd_sources(a):
    rows = []
    for name, mod in sorted(sources.available().items()):
        doc = (mod.__doc__ or "").strip().splitlines()
        rows.append({"source": name, "about": doc[0] if doc else "",
                     "presets": sorted((getattr(mod, "PRESETS", None) or {}).keys())})

    def human(rows):
        for r in rows:
            pre = f"  presets: {', '.join(r['presets'])}" if r["presets"] else ""
            print(f"  {r['source']:<11} {r['about']}{pre}")
    _out(rows, a.json, human)


def main(argv=None):
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    p = argparse.ArgumentParser(prog="jobhunt", parents=[common])
    sub = p.add_subparsers(dest="cmd", required=True)

    def cmd(name, **kw):
        return sub.add_parser(name, parents=[common], **kw)

    s = cmd("discover", help="fetch open roles from all (or some) companies")
    s.add_argument("company", nargs="*")
    s.add_argument("--no-filter", action="store_true", help="store everything, skip profile prefilter")
    s.set_defaults(fn=cmd_discover)

    s = cmd("jobs", help="list stored jobs")
    s.add_argument("--status", default="new", choices=(*store.STATUSES, "all"))
    s.add_argument("--company")
    s.add_argument("--since", help="ISO date: only jobs first seen on/after")
    s.add_argument("--limit", type=int)
    s.add_argument("--full", action="store_true", help="include descriptions")
    s.set_defaults(fn=cmd_jobs)

    s = cmd("show", help="show one job with its full description")
    s.add_argument("uid")
    s.set_defaults(fn=cmd_show)

    s = cmd("status", help="move job(s) through the pipeline")
    s.add_argument("status", choices=store.STATUSES)
    s.add_argument("uid", nargs="+")
    s.add_argument("--score", type=float)
    s.add_argument("--notes")
    s.set_defaults(fn=cmd_status)

    s = cmd("prepare", help="create an application folder for a job")
    s.add_argument("uid")
    s.set_defaults(fn=cmd_prepare)

    s = cmd("render", help="render cv.md / cover_letter.md in an application folder to PDF")
    s.add_argument("dir")
    s.set_defaults(fn=cmd_render)

    s = cmd("add", help="add a company (built-in preset, or auto-detected Greenhouse/Lever/Ashby board)")
    s.add_argument("name")
    s.add_argument("--url", help="careers page URL")
    s.add_argument("--key")
    s.add_argument("--source", help="skip detection, e.g. greenhouse")
    s.add_argument("--board", help="board slug for greenhouse/lever/ashby")
    s.set_defaults(fn=cmd_add)

    s = cmd("remove", help="remove companies from companies.yaml (stored jobs are kept)")
    s.add_argument("key", nargs="+")
    s.set_defaults(fn=cmd_remove)

    s = cmd("companies", help="list configured companies")
    s.set_defaults(fn=cmd_companies)

    s = cmd("sources", help="list available sources and their built-in company presets")
    s.set_defaults(fn=cmd_sources)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
