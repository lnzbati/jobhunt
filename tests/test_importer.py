"""Offline tests for single-link import (schema.org JobPosting parsing and key mapping)."""
import json

from jobhunt.importer import ImportContext, _fallback, _from_json_ld, _job_postings

POSTING = {
    "@context": "https://schema.org", "@type": "JobPosting", "title": "Platform Engineer",
    "description": "<p>Build things &amp; ship them.</p>", "datePosted": "2026-11-01",
    "identifier": {"@type": "PropertyValue", "value": "REQ-42"},
    "hiringOrganization": {"@type": "Organization", "name": "Acme Robotics"},
    "jobLocation": [{"@type": "Place", "address": {"addressLocality": "London", "addressCountry": "GB"}}],
    "responsibilities": ["Own the runtime", "Mentor"],
}


def page(obj) -> str:
    return f'<html><script type="application/ld+json">{json.dumps(obj)}</script></html>'


def test_job_posting_found_inside_graph():
    html = page({"@context": "https://schema.org", "@graph": [{"@type": "WebPage"}, POSTING]})
    assert [p["title"] for p in _job_postings(html)] == ["Platform Engineer"]


def test_json_ld_to_job():
    job = _from_json_ld("https://careers.acme.dev/jobs/42", page(POSTING), ImportContext([]))
    assert (job.uid, job.title, job.locations) == ("acmerobotics:REQ-42", "Platform Engineer", ["London, GB"])
    assert "Build things & ship them." in job.description and "- Own the runtime" in job.description


def test_key_for_prefers_configured_company():
    ctx = ImportContext([{"key": "acme", "name": "Acme Robotics", "source": "ashby", "board": "acme-robotics"}])
    assert ctx.key_for("ashby", board="acme-robotics") == "acme"
    assert ctx.key_for("link", name="acme robotics") == "acme"
    assert ctx.key_for("lever", board="other") == "other"


def test_fallback_flags_review():
    job = _fallback("https://www.example.com/careers/x", "<title>Role X</title><p>About</p>", ImportContext([]))
    assert job.meta["needs_review"] and job.title == "Role X" and job.company == "example"
