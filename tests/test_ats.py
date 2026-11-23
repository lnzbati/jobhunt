"""Offline tests for the ATS plan/check logic (no PDF rendering needed)."""
from pathlib import Path

from jobhunt import ats
from jobhunt.ats import contains, normalise


def test_matching_handles_word_endings_and_symbols():
    text = normalise("Mentored 3 engineers. Managed C++ and Node.js services; built CI/CD on GCP.")
    assert contains(text, "mentoring") and contains(text, "mentor") and contains(text, "managing")
    assert not contains(text, "management")  # a different word to an ATS: don't overstate coverage
    assert contains(text, "C++") and contains(text, "Node.js") and contains(text, "GCP")
    assert not contains(text, "C") and not contains(text, "Java")
    assert not contains(normalise("JavaScript"), "Java")


def test_ligatures_are_normalised():
    assert contains(normalise("built the ﬁrst ﬂow"), "first flow")


def test_keywords_file_parsing(tmp_path: Path):
    (tmp_path / "keywords.md").write_text("# comment\n!Java | Scala\n- Kafka\n\n")
    terms = ats.read_keywords(tmp_path / "keywords.md")
    assert [(t.label, t.variants, t.must) for t in terms] == [("Java", ["Java", "Scala"], True),
                                                            ("Kafka", ["Kafka"], False)]


def test_plan_splits_supported_and_gaps(tmp_path: Path):
    (tmp_path / "jd.md").write_text("Backend role")
    (tmp_path / "keywords.md").write_text("!Java\nKafka\nmentoring\n")
    rep = ats.plan(tmp_path, "- Led streaming migration (Kafka). Mentored 3 engineers.")
    assert rep.supported_missing == ["Kafka", "mentoring"] and rep.gaps == ["Java"]
    assert "**Java** (must-have)" in ats.to_markdown(rep, "plan")


def test_parse_checks_flag_problems():
    me = {"name": "Alex Example", "email": "alex@example.com", "phone": "+44 7700 900000"}
    good = ("Alex Example\nalex@example.com · +44 7700 900000\nEXPERIENCE\nEngineer · Jan 2022 – Present\n"
            "EDUCATION\nMSc\nSKILLS\nPython " + "word " * 300)
    levels = {c["msg"]: c["level"] for c in ats.parse_checks(good, 1, me)}
    assert all(v == "ok" for v in levels.values()), levels
    bad = ats.parse_checks("Summary\nthe ﬁrst\n2020 - 2021", 3, me)
    assert {c["level"] for c in bad} >= {"fail", "warn"}
    assert any("ligatures" in c["msg"] or "break ATS" in c["msg"] for c in bad if c["level"] == "fail")
