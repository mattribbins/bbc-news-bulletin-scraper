# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use the `.venv` virtual environment. The Makefile wraps the common ones.

```bash
# Install dev dependencies
make install-dev

# Format code (must be run before committing or linting)
make format

# Run all linters (flake8, mypy, pylint)
make lint

# Run black check and isort check explicitly (matches CI)
.venv/bin/python -m black --check --diff src/ tests/
.venv/bin/python -m isort --check-only --diff src/ tests/

# Run tests
make test

# Run a single test file or test function
.venv/bin/python -m pytest tests/test_basic.py -v
.venv/bin/python -m pytest tests/test_basic.py::TestAudioProcessor::test_lufs_normalisation -v

# Run security checks
make security

# Run everything (format + lint + security + test)
make check

# Run locally (uses config/config-local.yaml)
make run

# Docker (Debian is the primary build; Alpine is temporarily disabled)
make docker-build-debian
make docker-run
```

## Mandatory before pushing

1. **`make format`** — always run before linting. Black line length is 88 chars. CI fails on formatting drift.
2. **`make lint`** — flake8, mypy, pylint must all pass.
3. **`make test`** — pytest with coverage.

CI runs these in order: format check → lint → security → test → docker build.

## Architecture

The application downloads BBC radio bulletins on a schedule, processes the audio, and writes a single output file per programme that is overwritten on each new bulletin.

**Data flow:**
```
scheduler.py (APScheduler cron) 
  → scraper.py (get_iplayer CLI) 
  → audio_processor.py (ffmpeg) 
  → output/{programme_name}.wav
```

**Component responsibilities:**

- `main.py` — wires everything together, handles SIGINT/SIGTERM, detects Docker vs. local paths
- `config_manager.py` — loads and validates YAML config; searches `config/config-local.yaml` → `config/config.yaml` → `/app/config/config.yaml`
- `scraper.py` — builds and runs `get_iplayer` commands, handles its return codes (0=ok, 1/6=partial — check for files anyway), tracks processed episode PIDs to prevent reprocessing, clears the downloads directory on startup
- `audio_processor.py` — wraps ffmpeg with atomic writes (UUID temp file → `replace()`) and lock files to prevent race conditions; skips processing if the output file already exists
- `scheduler.py` — APScheduler background scheduler; optionally triggers a download immediately on startup (`download_on_startup`)
- `health_monitor.py` — optional HTTP server (default port 8080) with `/health`, `/status`, `/metrics` endpoints

## Key behaviours to be aware of

**get_iplayer exit codes:** Return code 6 is not a hard failure — it means all episodes in the batch failed (usually expired content), but one or more files may still have downloaded before that. Always check for files on codes 0, 1, and 6.

**Episode deduplication:** Processed PIDs are written to `.get_iplayer/processed_pids.txt`. PIDs are extracted from get_iplayer's output filenames (e.g. `News_Update_for_Somerset_-_09_30_Update_p0nldk7z_original.m4a`). `--force` and `--overwrite` are intentionally absent from the get_iplayer command so its own history also prevents re-downloads.

**Startup cleanup:** `scraper.py` deletes all audio files from the downloads directory on startup. Stale files from a previous run cannot be trusted.

**Output is overwritten:** Each programme has a single fixed output filename (e.g. `somerset_update.wav`). The audio processor returns `True` immediately if the output file already exists — meaning a file from a prior run will block processing of a newly downloaded episode until the output file is removed or replaced.

**Per-programme trim overrides:** `trim_start_seconds` and `trim_end_seconds` can be set at the programme level in config, overriding the global audio settings.

## Configuration

`config/config-local.yaml` is used for local development (DEBUG logging, local paths). `config/config.yaml` is production (Docker paths). The `BBC_CONFIG` environment variable overrides the search path.

Programmes need a `url` pointing to a BBC series/brand PID (e.g. `https://www.bbc.co.uk/programmes/p08dy4zh`). Set `pid_recursive: true` so get_iplayer fetches individual episodes from the series. `since` and `available_since` control how far back to look.

## Releases

Tags matching `v*.*.*` trigger the release workflow, which builds a multi-arch (amd64 + arm64) Debian image and pushes it to ghcr.io, then creates a GitHub Release with an auto-generated changelog. The Alpine build is currently disabled in CI and the release workflow.

Version is defined in `pyproject.toml` and should be bumped (patch/minor/major) before tagging.

## Python version matrix

CI tests against 3.11, 3.12, 3.13, and 3.14-dev. The `3.14-dev` job has `continue-on-error: true` as it is pre-release and package compatibility is not guaranteed. Lint and security jobs pin to 3.11.
