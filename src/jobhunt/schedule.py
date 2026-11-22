"""Scheduled runs via cron (macOS and Linux).

Each schedule is one crontab line tagged `# jobhunt:<name>`. jobhunt only ever touches its
own tagged lines. The line calls `jobhunt run-scheduled <task>`, which does the work and logs
to data/logs/scheduled.log.

Tasks (never submit an application; that always needs you):
  discover  fetch new roles and write a digest. No model calls, free.
  score     discover, then headless Claude Code scores new roles and updates the shortlist
            (`claude -p "/job-hunt score"`). Uses model usage and needs the `claude` CLI.
"""
from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

from . import config

TASKS = {
    "discover": "fetch new roles and write a digest (no model calls)",
    "score": "discover, then let Claude score and shortlist new roles (uses model usage)",
}
TAG = "# jobhunt:"
DAYS = {"daily": "*", "weekdays": "1-5", "weekends": "0,6"}
_DOW = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}

# What the unattended Claude run may do: read files and run the jobhunt CLI. Nothing else,
# so it can score and shortlist but cannot browse, edit files or apply.
CLAUDE_ALLOWED_TOOLS = ["Read", "Grep", "Glob", "Bash(uv run jobhunt:*)"]


@dataclass
class Entry:
    name: str
    line: str


def parse_time(at: str) -> tuple[int, int]:
    m = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", at.strip())
    if not m:
        raise ValueError(f"--at must be HH:MM (24h), got {at!r}")
    return int(m.group(1)), int(m.group(2))


def parse_days(days: str) -> str:
    days = days.strip().lower()
    if days in DAYS:
        return DAYS[days]
    try:
        nums = sorted({_DOW[d.strip()[:3]] for d in days.split(",")})
    except KeyError as e:
        raise ValueError(f"--days must be daily, weekdays, weekends or e.g. mon,wed,fri (got {days!r})") from e
    return ",".join(str(n) for n in nums)


def build_line(name: str, task: str, at: str, days: str, notify: bool, claude: str | None = None) -> str:
    if task not in TASKS:
        raise ValueError(f"unknown task {task!r}; choose from {', '.join(TASKS)}")
    hour, minute = parse_time(at)
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv not found on PATH")
    # cron starts with a bare PATH: pin the directories of the tools we need
    path_dirs = [os.path.dirname(uv), "/usr/local/bin", "/opt/homebrew/bin", "/usr/bin", "/bin"]
    env = {"PATH": ":".join(dict.fromkeys(path_dirs))}
    if task == "score":
        claude = claude or shutil.which("claude")
        if not claude or not os.access(claude, os.X_OK):
            raise RuntimeError(
                "`score` needs a working Claude Code CLI. Install it (https://docs.claude.com/en/docs/claude-code) "
                "so `claude --version` works in a terminal, or pass --claude /path/to/claude.")
        env["JOBHUNT_CLAUDE"] = claude
        env["PATH"] = os.path.dirname(claude) + ":" + env["PATH"]
    log = config.DATA_DIR / "logs" / "scheduled.log"
    cmd = f"{shlex.quote(uv)} run --project {shlex.quote(str(config.ROOT))} jobhunt run-scheduled {task}"
    if notify:
        cmd += " --notify"
    env_s = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    return (f"{minute} {hour} * * {parse_days(days)} cd {shlex.quote(str(config.ROOT))} && "
            f"mkdir -p {shlex.quote(str(log.parent))} && {env_s} {cmd} >> {shlex.quote(str(log))} 2>&1 "
            f"{TAG}{name}")


# --- crontab text manipulation (pure, unit-tested) ---------------------------------------

def entries(crontab: str) -> list[Entry]:
    out = []
    for line in crontab.splitlines():
        if TAG in line:
            out.append(Entry(name=line.rsplit(TAG, 1)[1].strip(), line=line))
    return out


def upsert(crontab: str, name: str, line: str) -> str:
    kept = [ln for ln in crontab.splitlines() if not ln.rstrip().endswith(f"{TAG}{name}")]
    kept.append(line)
    return "\n".join(kept).strip("\n") + "\n"


def remove(crontab: str, name: str) -> tuple[str, bool]:
    lines = crontab.splitlines()
    kept = [ln for ln in lines if not ln.rstrip().endswith(f"{TAG}{name}")]
    return ("\n".join(kept).strip("\n") + "\n") if kept else "", len(kept) != len(lines)


def describe(line: str) -> str:
    minute, hour, _, _, dow = line.split()[:5]
    days = {v: k for k, v in DAYS.items()}.get(dow) or ",".join(
        {v: k for k, v in _DOW.items()}[int(d)] for d in dow.split(","))
    task = re.search(r"run-scheduled (\w+)", line)
    return f"{int(hour):02d}:{int(minute):02d} {days}: {task.group(1) if task else '?'}"


# --- crontab I/O ------------------------------------------------------------------------

def read_crontab() -> str:
    if not shutil.which("crontab"):
        raise RuntimeError("crontab not found. Scheduling needs cron (macOS or Linux).")
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""  # exit 1 = no crontab yet


def write_crontab(text: str) -> None:
    subprocess.run(["crontab", "-"], input=text, text=True, check=True)


# --- the scheduled run itself ------------------------------------------------------------

def _log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def notify(title: str, message: str) -> None:
    if sys.platform == "darwin" and shutil.which("osascript"):
        script = f"display notification {json_str(message)} with title {json_str(title)}"
        subprocess.run(["osascript", "-e", script], check=False)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", title, message], check=False)


def json_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def run_claude_scoring() -> int:
    claude = os.environ.get("JOBHUNT_CLAUDE") or shutil.which("claude")
    if not claude:
        _log("score: claude CLI not found, skipping scoring")
        return 1
    cmd = [claude, "-p", "/job-hunt score", "--allowedTools", *CLAUDE_ALLOWED_TOOLS]
    _log("score: " + " ".join(shlex.quote(c) for c in cmd))
    r = subprocess.run(cmd, cwd=config.ROOT, capture_output=True, text=True)
    if r.stdout.strip():
        print(r.stdout.strip(), flush=True)
    if r.returncode:
        _log(f"score: claude exited {r.returncode}: {r.stderr.strip()[:500]}")
    return r.returncode
