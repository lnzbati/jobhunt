"""Job sources. Every module in this package is a source, named after its file.

A source module exposes:

    fetch(company: dict, queries: list[str]) -> Iterable[Job]          (required)
        List open roles. Board-style ATSs (Greenhouse/Lever/Ashby) return the
        whole board and ignore `queries`; big custom sites search once per query.

    fetch_description(job: Job) -> str | None                          (optional)
        Full plain-text description when the listing omits it.

    COMPLETE_LISTING: bool = False                                     (optional)
        True if fetch() returns every open role (board APIs). Only then are roles that
        disappear from a fetch marked `closed`. Search-based sources with page caps or
        query-dependent results must leave this False.

    PRESETS: dict[str, dict]                                           (optional)
        Ready-made companies.yaml entries, keyed by company key, so that
        `jobhunt add "<Name>"` picks this source instead of probing ATSs.
        e.g. {"apple": {"name": "Apple"}}

`company` is one entry from companies.yaml: {key, name, source, ...source-specific fields,
site_filters (merged in from profile.yaml)}.

To add a source, drop a new module here. See docs/adding-a-source.md.
"""
from __future__ import annotations

import importlib
import pkgutil
from functools import cache
from types import ModuleType


@cache
def available() -> dict[str, ModuleType]:
    mods = {}
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith("_"):
            mods[info.name] = importlib.import_module(f"{__name__}.{info.name}")
    return mods


def get_source(name: str) -> ModuleType:
    mods = available()
    if name not in mods:
        raise KeyError(f"Unknown source '{name}'. Available: {', '.join(sorted(mods))}")
    return mods[name]


def presets() -> dict[str, dict]:
    """All built-in company presets: {key: {..., 'source': module name}}."""
    out = {}
    for name, mod in available().items():
        for key, cfg in (getattr(mod, "PRESETS", None) or {}).items():
            out[key] = {**cfg, "source": name}
    return out
