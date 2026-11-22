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

Two places sources are loaded from:

  src/jobhunt/sources/   built-in, shared, committed (this package)
  local_sources/         yours: gitignored, for sites only you care about. Same contract, but
                         use absolute imports (`from jobhunt.models import Job`). A local module
                         with the same name as a built-in one overrides it, which is handy for
                         patching a broken site before an upstream fix lands.
                         Override the folder with JOBHUNT_LOCAL_SOURCES=/some/dir.

See docs/adding-a-source.md.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import pkgutil
import sys
from functools import cache
from pathlib import Path
from types import ModuleType

LOCAL_PACKAGE = "jobhunt_local_sources"


def local_dir() -> Path:
    from ..config import ROOT
    return Path(os.environ.get("JOBHUNT_LOCAL_SOURCES") or ROOT / "local_sources")


def _load_local(path: Path) -> ModuleType:
    name = f"{LOCAL_PACKAGE}.{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    mod.__jobhunt_origin__ = "local"
    return mod


@cache
def available() -> dict[str, ModuleType]:
    mods = {}
    for info in pkgutil.iter_modules(__path__):
        if not info.name.startswith("_"):
            mod = importlib.import_module(f"{__name__}.{info.name}")
            mod.__jobhunt_origin__ = "built-in"
            mods[info.name] = mod
    d = local_dir()
    if d.is_dir():
        for path in sorted(d.glob("*.py")):
            if not path.name.startswith(("_", "test_")):
                mods[path.stem] = _load_local(path)  # local wins over a built-in of the same name
    return mods


def origin(mod: ModuleType) -> str:
    return getattr(mod, "__jobhunt_origin__", "built-in")


def get_source(name: str) -> ModuleType:
    mods = available()
    if name not in mods:
        raise KeyError(f"Unknown source '{name}'. Available: {', '.join(sorted(mods))}")
    return mods[name]


def presets() -> dict[str, dict]:
    """All company presets (built-in and local): {key: {..., 'source': module name}}."""
    out = {}
    for name, mod in available().items():
        for key, cfg in (getattr(mod, "PRESETS", None) or {}).items():
            out[key] = {**cfg, "source": name}
    return out
