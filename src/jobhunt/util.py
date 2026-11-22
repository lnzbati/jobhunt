from __future__ import annotations

import html
import re
from datetime import UTC, datetime

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def client(**kw) -> httpx.Client:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json, text/plain, */*"}
    headers.update(kw.pop("headers", {}))
    return httpx.Client(headers=headers, timeout=30, follow_redirects=True, **kw)


_TAG = re.compile(r"<[^>]+>")
_BLOCK = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr)[^>]*>", re.I)


def html_to_text(s: str | None) -> str | None:
    if not s:
        return s
    s = html.unescape(s)  # Greenhouse double-encodes
    s = _BLOCK.sub("\n", s)
    s = _TAG.sub("", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n\n", s)
    return s.strip()


def ms_to_iso(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=UTC).isoformat()
