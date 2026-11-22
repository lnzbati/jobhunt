"""Offline tests for the reverse-engineered parsers, using minimal fixtures shaped like the live sites."""
import json

from jobhunt.sources import apple, google, meta


def test_apple_hydration_decodes_js_string_literal():
    payload = {"loaderData": {"search": {"searchResults": [{"positionId": "1", "postingTitle": "Zürich SWE"}]}}}
    literal = json.dumps(json.dumps(payload))[1:-1]  # JSON inside a JS string literal
    html = f'<script>window.__staticRouterHydrationData = JSON.parse("{literal}");</script>'
    out = apple._hydration(html)
    assert out["loaderData"]["search"]["searchResults"][0]["postingTitle"] == "Zürich SWE"


def test_google_parser_survives_brackets_in_strings():
    row = ["123", "SWE [Infra]", "https://apply", [None, "<p>Use ] and [ freely</p>"], [None, "<li>BSc</li>"],
           "x", None, "DeepMind", "en", [["London, UK", []]], [None, "<p>About</p>"], [2], [1794838054, 0]]
    data = json.dumps([[row], None, 1, 20])
    html = "AF_initDataCallback({key: 'ds:1', hash: '2', data: " + data + ", sideChannel: {}});"
    rows, total, per = google._parse(html)
    job = google._to_job("google", rows[0])
    assert (total, per, job.title, job.team, job.locations) == (1, 20, "SWE [Infra]", "DeepMind", ["London, UK"])
    assert "Use ] and [ freely" in job.description


def test_meta_doc_id_pattern():
    bundle = ('__d("CareersJobSearchResultsDataQuery_candidate_portalRelayOperation",[],'
              '(function(t,n,r,o,a,i){a.exports="40084319704492118"}),null);')
    assert meta._OP.search(bundle).group(1) == "40084319704492118"

