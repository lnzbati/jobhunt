# Scheduling daily runs

jobhunt can check for new roles on its own every morning, so your list is waiting for you.
It uses **cron**, the built-in scheduler on macOS and Linux. jobhunt only adds and removes its
own lines, marked `# jobhunt:<name>`. Anything else in your crontab is left alone.

> [!IMPORTANT]
> Scheduled runs **never apply** for you. They find roles, and optionally score them. Applying
> always goes through `/apply`, with your approval for each application.

## Pick a task

| Task | What it does | Cost |
|---|---|---|
| `discover` | Fetches new roles from all your companies, filters them with your profile, and writes a digest to `data/digests/<date>.md`. | Free: no AI involved |
| `score` | Everything `discover` does, then runs Claude Code headlessly (`claude -p "/job-hunt score"`) to score new roles and update your shortlist. | Uses Claude model usage on every run |

The scoring run is locked down. Claude may only read files and run `uv run jobhunt …`, so
it can't browse, edit files or apply.

## Set it up

From the repo folder:

```bash
# Preview first: prints the exact cron line, changes nothing
uv run jobhunt schedule add --task discover --at 08:30 --days weekdays --notify --dry-run

# Then for real
uv run jobhunt schedule add --task discover --at 08:30 --days weekdays --notify
```

Or, in Claude Code, run `/job-hunt schedule` and answer a couple of questions.

| Option | Meaning | Default |
|---|---|---|
| `--task` | `discover` or `score` | `discover` |
| `--at` | Time of day, 24-hour `HH:MM` | `08:30` |
| `--days` | `daily`, `weekdays`, `weekends`, or a list like `mon,wed,fri` | `daily` |
| `--notify` | Desktop notification when it finishes (macOS, or Linux with `notify-send`) | off |
| `--claude` | Path to the `claude` CLI, for `score` if it isn't on your PATH | found on PATH |
| `--dry-run` | Show the cron line without installing it | off |
| name (positional) | Name of the schedule, to keep several | the task name |

You can have more than one, for example a free `discover` at 08:30 and a `score` run at 13:00:

```bash
uv run jobhunt schedule add morning --task discover --at 08:30
uv run jobhunt schedule add lunch --task score --at 13:00 --days weekdays
```

## Check and remove

```bash
uv run jobhunt schedule list             # what's scheduled
uv run jobhunt schedule remove morning   # remove one by name
uv run jobhunt digest                    # today's digest in the terminal
```

Logs from every scheduled run are in `data/logs/scheduled.log`. Digests are in `data/digests/`.

## Good to know

- **Your computer has to be awake.** Cron doesn't run while a laptop sleeps, and a missed
  run happens at the next scheduled time, not on wake. Pick a time you're usually at the desk.
- **macOS permissions.** If nothing appears in the log, give `cron` Full Disk Access in
  System Settings → Privacy & Security → Full Disk Access (add `/usr/sbin/cron`).
- **`score` needs a working `claude` CLI.** Check with `claude --version` in a terminal. The
  copy bundled inside the VS Code extension moves on every update, so install the CLI
  ([docs](https://docs.claude.com/en/docs/claude-code)) or pass `--claude <path>`.
- **Moving the repo** breaks the paths in the cron line. Run `schedule add` again from the new location.
- **Windows** has no cron. Use Task Scheduler to run
  `uv run --project <repo> jobhunt run-scheduled discover` at the time you want.
