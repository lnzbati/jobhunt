from __future__ import annotations

import os
import sys
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("JOBHUNT_ROOT", Path(__file__).resolve().parents[2]))
PROFILE_DIR = ROOT / "profile"
DATA_DIR = ROOT / "data"
APPS_DIR = ROOT / "applications"
TEMPLATES_DIR = ROOT / "templates"
COMPANIES = ROOT / "companies.yaml"            # yours, gitignored
COMPANIES_EXAMPLE = ROOT / "companies.example.yaml"


class ConfigError(SystemExit):
    pass


def _load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _read_companies() -> dict:
    return (_load_yaml(COMPANIES).get("companies") or {}) if COMPANIES.exists() else {}


def load_companies(include_disabled: bool = False) -> list[dict]:
    if not COMPANIES.exists():
        raise ConfigError(
            "No companies.yaml yet. Add companies with `jobhunt add \"<Name>\"`, "
            "or start from the example: cp companies.example.yaml companies.yaml"
        )
    out = [{**(cfg or {}), "key": key} for key, cfg in _read_companies().items()]
    return out if include_disabled else [c for c in out if c.get("enabled", True)]


def save_company(key: str, cfg: dict) -> Path:
    data = _load_yaml(COMPANIES) if COMPANIES.exists() else {}
    data.setdefault("companies", {})[key] = cfg
    _write(data)
    return COMPANIES


def remove_company(key: str) -> bool:
    data = _load_yaml(COMPANIES) if COMPANIES.exists() else {}
    if key not in (data.get("companies") or {}):
        return False
    del data["companies"][key]
    _write(data)
    return True


def _write(data: dict) -> None:
    header = ("# Your companies (gitignored). Manage with `jobhunt add` / `jobhunt remove`, or edit by hand.\n"
              "# Format and source types: see companies.example.yaml\n")
    with COMPANIES.open("w") as f:
        f.write(header)
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def load_profile() -> dict:
    """profile/profile.yaml, falling back (loudly) to the example so discovery can be tried out."""
    p = PROFILE_DIR / "profile.yaml"
    if not p.exists():
        print("warning: profile/profile.yaml not found, using profile.example.yaml placeholders "
              "(cp profile/profile.example.yaml profile/profile.yaml)", file=sys.stderr)
        p = PROFILE_DIR / "profile.example.yaml"
    return _load_yaml(p)
