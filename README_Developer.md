# mlx-whisper-batch — Developer notes

End-user install, config, and overnight usage: see [README.md](README.md).

This file covers local development, tests, and promoting a working tree to the stable pipx CLI.

## Requirements (dev)

Same as users: Apple Silicon, `ffmpeg` / `ffprobe`, Python 3.11+. Plus a clone of this repo.

## Develop and test in parallel

Keep a **stable** pipx install for overnight jobs, and a **venv** for development:

```bash
cd mlx-whisper-batch

# stable CLI (frozen copy inside pipx)
pipx install .

# editable Dev env
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
whisper-batch --dry-run /path/to/folder   # uses working tree
deactivate

# overnight still uses pipx until you promote:
whisper-batch /path/to/archive
# when happy:
pipx reinstall mlx-whisper-batch
```

With the venv activated, its `bin/` wins over `~/.local/bin`. Check with `which whisper-batch` if unsure.

Shortcut (one install always tracks the working tree): `pipx install --editable .` — convenient, but overnight will run unfinished edits.

## Editable install only

If you do not need a separate overnight pipx copy:

```bash
cd mlx-whisper-batch
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

`whisper-batch` and `whisper-fix-output-names` then resolve to the working tree.

## Tests

```bash
source .venv/bin/activate   # if not already
pytest
```

Pytest is configured in `pyproject.toml` (`testpaths = ["tests"]`, `pythonpath = ["src"]`). Dev extra: `pip install -e ".[dev]"` (pulls in `pytest>=8`).

## Package layout

```text
src/mlx_whisper_batch/
  cli.py          # whisper-batch entry
  fix_cli.py      # whisper-fix-output-names entry
  batch.py        # folder scan, orchestration, timing log
  transcribe.py   # chunked mlx-whisper + retry
  loops.py        # repeat-loop heuristics
  outputs.py      # .json / .txt write + truncated-name fix
  audio.py        # duration / format helpers
  settings.py     # TOML + CLI overrides
tests/            # pytest suite
whisper-batch.example.toml
pyproject.toml    # hatchling, scripts, optional [dev]
```

Entry points (from `pyproject.toml`):

- `whisper-batch` → `mlx_whisper_batch.cli:main`
- `whisper-fix-output-names` → `mlx_whisper_batch.fix_cli:main`

## Promote to pipx

When the editable tree looks good for overnight use:

```bash
deactivate   # optional; pipx does not need the venv
pipx reinstall mlx-whisper-batch
# or from the repo root: pipx install . --force
which whisper-batch   # expect ~/.local/bin/whisper-batch
```

That freezes the current tree into pipx again (`reinstall` uses the package/environment name `mlx-whisper-batch`, not `.` or the CLI name). Further edits stay in the venv until the next reinstall.
