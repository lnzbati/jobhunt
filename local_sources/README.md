# local_sources/: your personal careers-site sources

Put sources here for sites that only you care about. Everything in this folder **except
this README** is gitignored, so your sources stay on your machine.

- Same contract as the built-in ones (`src/jobhunt/sources/__init__.py`), but use
  **absolute imports**: `from jobhunt.models import Job`, `from jobhunt.util import client`.
- `<name>.py` becomes source `<name>`. Point a company at it in `companies.yaml`
  (`source: <name>`), or give it a `PRESETS` entry and run `jobhunt add "<Company>"`.
- A local source with the same name as a built-in one **replaces** it. Use that to patch
  a broken site before the upstream fix lands.
- Tests go next to it as `test_<name>.py`. Run them with `uv run pytest local_sources`.
- `uv run jobhunt sources` marks local ones with `[local]`.

Built something others would use too? Move it to `src/jobhunt/sources/` (switching to
relative imports), add tests under `tests/`, and open a PR. See `docs/adding-a-source.md`.
