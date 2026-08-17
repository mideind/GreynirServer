# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

GreynirServer is the web API and frontend for **GreynirEngine** (the `reynir`
package), a parser for Icelandic. It also runs a scraper/parser pipeline that
ingests Icelandic news into PostgreSQL. It is an *application*, not a library:
modules live at the repository root and are run in place
(`[tool.uv] package = false`).

Production is `greynir.is`, on a single host, `frida.mideind.is`.

## Environment

- **CPython 3.14** in production. `requires-python = ">=3.11"`. CI tests
  CPython 3.14 only; the PyPy leg was dropped 2026-08-17, so the 3.11 floor
  is nominal rather than CI-enforced.
- **Dependencies are managed with `uv` and pinned in `uv.lock`.** There is no
  `requirements.txt` — it was deleted once `deploy.sh` moved to `uv sync`.
  Do not reintroduce one.
- `uv sync` for a dev environment, `uv sync --frozen --no-dev` for anything
  production-shaped. `--no-dev` matters: `sqlalchemy-stubs` declares `mypy`,
  which drags in a Rust/PyO3 extension that fails to build in some environments.
- **Always pass `--python`** when it matters. uv otherwise selects the newest
  interpreter it can find, which on a dev box may be a beta.
- `icespeak` is tracked from git `master`, not PyPI, because the latest release
  pins `pydantic==2.3.0`, which cannot be installed on Python 3.13+.

## Running tests

```bash
uv run python -m pytest
```

**⚠ Never run the test suite on the production host.** The database name is
hardcoded as `scraper` in `db/__init__.py` — only host and port are
configurable — so a test run there writes to the live database. Use
`scripts/test_local.sh`, which exists for exactly this. If you are on
`frida.mideind.is`, let CI run the tests instead.

CI also gates on these, so run them before claiming a change is done:

```bash
shellcheck -x scripts/*.sh          # any change under scripts/
uv run curlylint templates/*        # any template change
jshint static/js/common.js          # any JS change
```

`bash -n` is not a substitute for `shellcheck`.

## Deployment

`scripts/deploy.sh` deploys production; `scripts/deploy.sh staging` deploys
staging. It installs with `uv sync --frozen --no-dev` and restarts the service.

- **It must be run by the user that owns the deployment** (`greynir`). It
  enforces this. Group membership is not enough — files inside `$DEST` are
  owner-writable only.
- **Deployment venvs are symlinks** (`venv -> cp314`). An interpreter change
  means building a new venv alongside, repointing the symlink and restarting;
  rollback is repointing it back. No systemd unit names an interpreter.
- Two separate targets. `deploy.sh` handles the web apps under
  `/usr/share/nginx/`. The cron pipeline and the similarity server run from a
  *different* checkout and are updated only by `git pull` — neither implies the
  other.
- `config/Greynir.conf` and `.env` are **not** copied by `deploy.sh`; they are
  per-environment.

## Things that will bite you

- **A gunicorn worker takes 30–80 s to import** before a boot failure surfaces,
  so `systemctl status` looks healthy in that window. Wait past it before
  believing a deploy worked. A fresh venv is at the slow end, because startup
  recompiles the grammar.
- **`config/Greynir.conf` silently overrides environment variables.**
  `settings.py` reads `GREYNIR_HOST`/`GREYNIR_PORT`/`GREYNIR_DB_HOST` from the
  environment at class-definition time, then `Settings.read()` overwrites them
  from the file.
- **A systemd drop-in beats `.env`.** `main.py` calls `load_dotenv()`, which
  defaults to `override=False`, so anything already in the environment wins.
  Editing a drop-in needs `systemctl daemon-reload`; a bare restart re-reads
  nothing.
- **`vectors/` is stuck on CPython 3.9.** The topic tagger and the similarity
  server run from `vectors/venv` with `gensim==3.8.2`, which does
  `from collections import Mapping` — removed in Python 3.10 — so it cannot
  move without a gensim 4 port. That venv installs from
  `vectors/requirements.txt` with pip and is deliberately outside the lock.
  Code shared with it (`db/`, `settings.py`) must therefore stay importable on
  3.9. This is why `db/__init__.py` *detects* its Postgres driver rather than
  naming one: `psycopg2` on 3.14, `psycopg2cffi` on 3.9.
- **`similar.py` uses un-monkey-patched sockets on purpose.** Every call to the
  similarity server is a genuinely blocking syscall, which under gevent freezes
  the whole worker — all greenlets, not just the caller. A timeout there bounds
  an outage; it does not keep the app responsive. Do not put it behind a shared
  lock.
- **`similarity.service` has a ~16 minute warm-up** and does not serve during
  it. Restarting it is a scheduled degradation, not a routine bounce.
- **A `ScrapeHelper.get_content` that cannot find its container returns an
  empty document silently.** This destroyed 181,712 article bodies once and went
  unnoticed for ten months. If you touch `scrapers/`, make failure loud.

## Operational context

`/home/villi/PLAN.md` on `frida.mideind.is` is the live operations backlog for
the production host — open issues, migration recipes, and a long list of
hard-won gotchas. It is not in this repository. Read it before infrastructure,
deployment or database work, and treat its claims as dated rather than certain:
verify anything load-bearing, and correct it when you find it wrong.

`PLAN.md` in this repository is the working plan for retiring the similarity
server (`vectors/simserver.py`) in favour of pgvector. Read it before touching
`similar.py`, `search.py`, `vectors/`, or the `articles.topic_vector` /
`topic_embedding` columns, and keep its phase checkboxes and dated facts
current as the migration proceeds.

## Conventions

- Commit messages in this repository explain **why**, at length, including what
  was ruled out and what the alternative would have cost. Match that. A one-line
  summary of the diff is not the house style.
- Match the surrounding code's comment density and naming. Comments here tend to
  explain the non-obvious constraint rather than restate the code.
