"""ATS checks for a tailored CV: does it parse, and does it cover the job's key terms?

Two uses, both on an application folder:

  plan   (before writing the CV)  job's key terms vs master_facts.md:
           supported -> use it in the CV, in the job's wording
           gap       -> the facts don't support it: don't add it, note it in tailoring.md
  check  (after rendering)        text extracted from cv.pdf, the way an ATS reads it:
           parse checks (contact details, headings, dates, length, odd characters) and
           keyword coverage, split into covered / supported-but-missing / gaps

Key terms come from keywords.md in the folder, one per line, with alternatives separated by
`|` (e.g. `Kubernetes | k8s`) and an optional `!` prefix for must-haves. Without it, a
simple extractor picks terms from jd.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

STANDARD_HEADINGS = {
    "experience": ["experience", "work experience", "professional experience", "employment", "work history"],
    "education": ["education", "qualifications", "academic"],
    "skills": ["skills", "technical skills", "core skills", "competencies"],
}
LIGATURES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl"}
_DATE_RANGE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(19|20)\d{2}\s*[–—-]\s*"
    r"(((?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+)?(19|20)\d{2}|present|current|now)",
    re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


@dataclass
class Term:
    label: str
    variants: list[str]
    must: bool = False


@dataclass
class Report:
    terms: list[Term]
    covered: list[str] = field(default_factory=list)
    supported_missing: list[str] = field(default_factory=list)  # in facts, not in the CV
    gaps: list[str] = field(default_factory=list)                # not in the facts at all
    checks: list[dict] = field(default_factory=list)            # {level: ok|warn|fail, msg}
    source: str = ""


# --- text helpers ------------------------------------------------------------------------

def normalise(text: str) -> str:
    for lig, plain in LIGATURES.items():
        text = text.replace(lig, plain)
    return re.sub(r"\s+", " ", text).lower()


_SUFFIX = re.compile(r"(?:ing|ed|es|er|s|e)$")
_ENDINGS = r"(?:e|s|es|ed|ing|er|ers|ment|ments|ship)?"


def contains(text_norm: str, variant: str) -> bool:
    """Whole-word match, tolerant of word endings for single words (mentoring ~ mentored ~ mentor),
    and with boundaries that also work for C++, C#, .NET, Node.js."""
    v = normalise(variant).strip()
    if re.fullmatch(r"[a-z]{5,}", v):
        stem = _SUFFIX.sub("", v)
        pattern = rf"(?<![\w+#.]){re.escape(stem)}{_ENDINGS}(?![\w+#])"
    else:
        pattern = rf"(?<![\w+#.]){re.escape(v)}(?:s|es)?(?![\w+#])"
    return re.search(pattern, text_norm) is not None


def pdf_text(pdf: Path) -> tuple[str, int]:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    return "\n".join(page.extract_text() or "" for page in reader.pages), len(reader.pages)


# --- key terms ---------------------------------------------------------------------------

def read_keywords(path: Path) -> list[Term]:
    terms = []
    for line in path.read_text().splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line or line.startswith("#"):
            continue
        must = line.startswith("!")
        parts = [p.strip() for p in line.lstrip("!").split("|") if p.strip()]
        if parts:
            terms.append(Term(label=parts[0], variants=parts, must=must))
    return terms


_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it", "of",
    "on", "or", "our", "that", "the", "their", "this", "to", "we", "will", "with", "you", "your", "role",
    "team", "work", "working", "experience", "years", "year", "ability", "strong", "excellent", "including",
    "such", "about", "across", "within", "using", "use", "other", "new", "more", "help", "who", "what", "how",
    "able", "etc", "job",
}
_TECHY = re.compile(r"\b(?:[A-Za-z]+[+#]+|[A-Za-z]*[a-z][A-Z][A-Za-z]*|[A-Z]{2,}[a-z]?s?|[A-Za-z]+\.(?:js|NET|io)|"
                    r"[A-Za-z]+\d+[A-Za-z]*)(?![\w+#])")


_PROCESS = re.compile(r"\b(interview|hiring|recruit|apply|application|benefits?|salary|equal|employer|"
                      r"diversity|accommodation|visa|process|opportunit)", re.IGNORECASE)


def extract_keywords(jd: str, limit: int = 25) -> list[Term]:
    """Fallback when there's no keywords.md: requirement-section tokens that look like skills,
    plus repeated two-word phrases. Deliberately simple; keywords.md written by Claude is better."""
    m = re.search(r"(?is)(qualifications|requirements|what you.ll bring|about you|skills|you have|"
                  r"minimum|preferred).*", jd)
    focus = m.group(0) if m else jd
    counts: dict[str, int] = {}
    for tok in _TECHY.findall(focus):
        if tok.lower() not in _STOP and len(tok) > 1:
            counts[tok] = counts.get(tok, 0) + 3
    words = [w for w in re.findall(r"[a-z][a-z-]+", focus.lower())]
    for a, b in zip(words, words[1:], strict=False):
        if a not in _STOP and b not in _STOP and len(a) > 2 and len(b) > 2:
            counts[f"{a} {b}"] = counts.get(f"{a} {b}", 0) + 1
    ranked = [t for t, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n >= 2]
    seen, out = set(), []
    for t in ranked:
        key = t.lower().rstrip("s")  # API / APIs count once
        if key not in seen and not _PROCESS.search(t):
            seen.add(key)
            out.append(Term(label=t, variants=[t]))
        if len(out) >= limit:
            break
    return out


def load_terms(app_dir: Path) -> tuple[list[Term], str]:
    kw = app_dir / "keywords.md"
    if kw.exists():
        return read_keywords(kw), "keywords.md"
    jd = (app_dir / "jd.md").read_text() if (app_dir / "jd.md").exists() else ""
    return extract_keywords(jd), "extracted from jd.md (write keywords.md for better results)"


# --- plan and check ----------------------------------------------------------------------

def plan(app_dir: Path, facts: str) -> Report:
    terms, source = load_terms(app_dir)
    facts_n = normalise(facts)
    rep = Report(terms=terms, source=source)
    for t in terms:
        (rep.supported_missing if any(contains(facts_n, v) for v in t.variants) else rep.gaps).append(t.label)
    return rep


def check(app_dir: Path, facts: str, me: dict) -> Report:
    pdf = app_dir / "cv.pdf"
    if not pdf.exists():
        raise FileNotFoundError(f"{pdf} not found: render the CV first (jobhunt render)")
    text, pages = pdf_text(pdf)
    rep = plan(app_dir, facts)
    cv_n = normalise(text)
    in_facts = set(rep.supported_missing)
    rep.supported_missing, rep.gaps = [], []
    for t in rep.terms:
        if any(contains(cv_n, v) for v in t.variants):
            rep.covered.append(t.label)
        elif t.label in in_facts:
            rep.supported_missing.append(t.label)
        else:
            rep.gaps.append(t.label)
    rep.checks = parse_checks(text, pages, me)
    return rep


def parse_checks(text: str, pages: int, me: dict) -> list[dict]:
    out = []

    def add(level, msg):
        out.append({"level": level, "msg": msg})

    norm = normalise(text)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        add("fail", "No text could be extracted: the PDF would look empty to an ATS")
        return out
    name = (me.get("name") or "").strip()
    if name:
        first = normalise(" ".join(lines[:2]))
        add("ok" if normalise(name) in first else "warn",
            "Name is at the top" if normalise(name) in first else "Name isn't in the first lines of extracted text")
    email = (me.get("email") or "").strip().lower()
    if email:
        found = [e.lower().rstrip(".") for e in _EMAIL.findall(text)]
        add("ok" if email in found else "fail",
            "Email extracts intact" if email in found else f"Email {email} doesn't extract intact")
    phone = re.sub(r"\D", "", me.get("phone") or "")
    if phone:
        ok = phone[-8:] in re.sub(r"\D", "", text)
        add("ok" if ok else "warn", "Phone extracts intact" if ok else "Phone number doesn't extract intact")
    for key, names in STANDARD_HEADINGS.items():
        ok = any(re.search(rf"(^|\n)\s*{n}\s*(\n|$)", text, re.IGNORECASE) for n in names)
        add("ok" if ok else "warn",
            f"'{key.title()}' section found" if ok else f"No standard '{key.title()}' heading (ATSs look for it)")
    ranges = _DATE_RANGE.findall(text)
    add("ok" if ranges else "warn",
        f"{len(ranges)} date ranges parse" if ranges else "No date ranges like 'Jan 2022 – Present' found")
    if ranges and not any(r[0] for r in ranges):
        add("warn", "Dates are years only: ATSs compute tenure better with months (if the facts have them)")
    add("ok" if pages <= 2 else "warn", f"{pages} page(s)" + ("" if pages <= 2 else ": more than two"))
    odd = sorted({c for c in text if c in LIGATURES or 0xE000 <= ord(c) <= 0xF8FF})
    add("ok" if not odd else "fail",
        "No ligatures or icon glyphs" if not odd else f"Characters that break ATS search: {' '.join(odd)}")
    words = len(norm.split())
    add("ok" if 250 <= words <= 1100 else "warn", f"{words} words" + (
        "" if 250 <= words <= 1100 else ": unusually short" if words < 250 else ": long for a CV"))
    return out


def to_markdown(rep: Report, mode: str) -> str:
    n = len(rep.terms) or 1
    lines = [f"# ATS {mode}", "", f"_Key terms: {rep.source}_", ""]
    if mode == "check":
        reachable = len(rep.covered) + len(rep.supported_missing)
        pct = round(100 * len(rep.covered) / n)
        lines += [f"**Coverage:** {len(rep.covered)}/{len(rep.terms)} key terms ({pct}%). "
                  f"Reachable with your facts: {reachable}/{len(rep.terms)}.", ""]
        lines += ["## Parsing", ""] + [
            f"- {'✅' if c['level'] == 'ok' else '⚠️' if c['level'] == 'warn' else '❌'} {c['msg']}" for c in rep.checks]
        lines += ["", "## Covered", "", ", ".join(rep.covered) or "_none_", ""]
    musts = {t.label for t in rep.terms if t.must}

    def fmt(items):
        return ", ".join(f"**{i}** (must-have)" if i in musts else i for i in items) or "_none_"
    lines += ["## In your facts but not in the CV: use them" if mode == "check" else
              "## Supported by your facts: use these, in the job's wording", "", fmt(rep.supported_missing), ""]
    lines += ["## Gaps: not in your facts, so don't add them", "",
              "Mention relevant ones in tailoring.md, or in the cover letter as something you'd learn.", "",
              fmt(rep.gaps), ""]
    return "\n".join(lines)
