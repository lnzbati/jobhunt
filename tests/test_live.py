"""Live smoke tests against the real careers sites. Opt in: JOBHUNT_LIVE=1 uv run --extra dev pytest -m live

Run these when `discover` reports an error, or before a release: the reverse-engineered
sources break when the sites change.
"""
import os

import pytest

from jobhunt.sources import get_source

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("JOBHUNT_LIVE"), reason="set JOBHUNT_LIVE=1 to hit real sites"),
]

CASES = [
    ({"key": "stripe", "source": "greenhouse", "board": "stripe"}, []),
    ({"key": "palantir", "source": "lever", "board": "palantir"}, []),
    ({"key": "cohere", "source": "ashby", "board": "cohere"}, []),
    ({"key": "apple", "source": "apple", "site_filters": {"location": "united-kingdom-GBR", "max_pages": 1}},
     ["software engineer"]),
    ({"key": "google", "source": "google", "site_filters": {"location": "London, UK", "max_pages": 1}},
     ["software engineer"]),
    ({"key": "microsoft", "source": "eightfold", "base_url": "https://apply.careers.microsoft.com",
      "domain": "microsoft.com", "site_filters": {"max_pages": 1}}, ["software engineer"]),
    ({"key": "meta", "source": "meta"}, ["software engineer"]),
]


@pytest.mark.parametrize(("company", "queries"), CASES, ids=[c["key"] for c, _ in CASES])
def test_source_returns_jobs_with_descriptions(company, queries):
    src = get_source(company["source"])
    jobs = []
    for job in src.fetch(company, queries):
        jobs.append(job)
        if len(jobs) >= 3:
            break
    assert jobs, f"{company['key']}: no jobs returned. Has the site changed?"
    j = jobs[0]
    assert j.title and j.url.startswith("https://") and j.external_id
    desc = j.description or (src.fetch_description(j) if hasattr(src, "fetch_description") else None)
    assert desc and len(desc) > 200, f"{company['key']}: no usable description"
