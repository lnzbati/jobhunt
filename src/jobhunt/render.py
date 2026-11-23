"""Render tailored markdown (cv.md, cover_letter.md) to PDF via headless Chromium.

Install once:  uv sync --extra pdf && uv run playwright install chromium
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import markdown
from jinja2 import Environment, FileSystemLoader

from .config import TEMPLATES_DIR, load_profile

DOCS = {"cv.md": "cv.html", "cover_letter.md": "cover_letter.html"}


def _html(md_text: str, template: str, profile: dict) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=False)
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    return env.get_template(template).render(body=body, me=profile.get("me") or {})


def render_dir(app_dir: str | Path) -> dict:
    app_dir = Path(app_dir)
    profile = load_profile()
    pages = {}
    for md_name, tpl in DOCS.items():
        src = app_dir / md_name
        if src.exists():
            out = src.with_suffix(".html")
            out.write_text(_html(src.read_text(), tpl, profile))
            pages[md_name] = out

    if not pages:
        return {"rendered": [], "error": f"no cv.md or cover_letter.md in {app_dir}"}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"rendered": [str(p) for p in pages.values()],
                "warning": "playwright not installed; produced HTML only. "
                           "Run: uv sync --extra pdf && uv run playwright install chromium"}

    pdfs = []
    name = (profile.get("me") or {}).get("name") or ""
    stem = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-") or None
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for html_path in pages.values():
            pdf = html_path.with_suffix(".pdf")
            page.goto(html_path.resolve().as_uri())
            page.pdf(path=str(pdf), format="A4", print_background=True,
                     margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"})
            pdfs.append(str(pdf))
            if stem:  # recruiters see the uploaded file's name: "Alex-Example-CV.pdf", not "cv.pdf"
                label = "CV" if pdf.stem == "cv" else "Cover-Letter"
                named = pdf.with_name(f"{stem}-{label}.pdf")
                shutil.copyfile(pdf, named)
                pdfs.append(str(named))
        browser.close()
    return {"rendered": pdfs}
