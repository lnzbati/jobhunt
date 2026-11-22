from jobhunt import store
from jobhunt.detect import _from_text
from jobhunt.filters import matches
from jobhunt.models import Job

SEARCH = {
    "title_include": ["engineer"],
    "title_exclude": ["intern", "manager"],
    "locations": ["London", "UK"],
    "remote_ok": True,
    "remote_regions": ["Europe", "EMEA"],
}


def job(title="Software Engineer", locations=("London",), remote=None, **kw):
    return Job(company="acme", source="greenhouse", external_id=kw.pop("id", "1"), title=title,
               url="https://x", locations=list(locations), remote=remote, **kw)


def test_title_include_exclude():
    assert matches(job(), SEARCH)
    assert not matches(job(title="Account Executive"), SEARCH)
    assert not matches(job(title="Engineering Manager, Infra"), SEARCH)
    assert not matches(job(title="Software Engineer Intern"), SEARCH)


def test_location_word_boundaries():
    assert matches(job(locations=["London, United Kingdom"]), SEARCH)
    assert not matches(job(locations=["New York, NY"]), SEARCH)
    assert not matches(job(locations=["Ukiah, CA"]), SEARCH)  # "UK" must not match "Ukiah"


def test_remote_needs_a_matching_region():
    assert not matches(job(locations=["New York, NY"], remote=True), SEARCH)
    assert matches(job(locations=["Remote - EMEA"], remote=True), SEARCH)


def test_detect_from_urls():
    assert _from_text("https://boards.greenhouse.io/anthropic/jobs/1") == ("greenhouse", "anthropic")
    assert _from_text("https://job-boards.greenhouse.io/waymo") == ("greenhouse", "waymo")
    assert _from_text("https://jobs.lever.co/spotify/abc") == ("lever", "spotify")
    assert _from_text("https://jobs.ashbyhq.com/wayve") == ("ashby", "wayve")
    assert _from_text("https://example.com/careers") is None


def test_store_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    db = store.connect()
    assert store.upsert(db, [job(id="1"), job(id="2")]) == (2, 0)
    assert store.upsert(db, [job(id="1")]) == (0, 1)
    store.set_status(db, "acme:1", "shortlisted", score=80)
    assert store.mark_closed(db, "acme", {"acme:1"}) == 1  # acme:2 vanished
    assert store.get(db, "acme:2")["status"] == "closed"
    assert store.query(db, status="shortlisted")[0]["score"] == 80


def test_sources_are_discovered_and_presets_resolve():
    from jobhunt import sources
    assert {"greenhouse", "lever", "ashby", "apple", "google", "meta", "eightfold"} <= set(sources.available())
    p = sources.presets()
    assert p["microsoft"]["source"] == "eightfold" and p["microsoft"]["domain"] == "microsoft.com"
    assert p["apple"]["source"] == "apple"


def test_companies_add_remove_roundtrip(tmp_path, monkeypatch):
    import pytest

    from jobhunt import config
    monkeypatch.setattr(config, "COMPANIES", tmp_path / "companies.yaml")
    with pytest.raises(config.ConfigError):
        config.load_companies()
    config.save_company("acme", {"name": "Acme", "source": "greenhouse", "board": "acme"})
    config.save_company("paused", {"name": "Paused", "source": "lever", "board": "p", "enabled": False})
    assert [c["key"] for c in config.load_companies()] == ["acme"]
    assert len(config.load_companies(include_disabled=True)) == 2
    assert config.remove_company("acme") and not config.remove_company("acme")


def test_slug_candidates_use_full_name_only():
    from jobhunt.detect import _slug_candidates
    assert _slug_candidates("Scale AI") == ["scaleai", "scale-ai"]
    assert _slug_candidates("Monzo") == ["monzo"]
