#!/usr/bin/env bash
#
# This is run once every morning by cron.
#
# It used to do two things: re-parse every article whose parser_version was
# older than the current one, then re-process whatever had been re-parsed.
# The RE-PARSE stage is decommissioned as of 2026-08-03 (see below); the
# re-process stage remains and is still required.
#

set -o errexit   # Exit when a command fails
# set -o nounset   # Disallow unset variables
set -o pipefail  # Pipeline command fails if any command fails

# Repository root, derived from this script's own location. Previously this was
# ~/Greynir, which resolved only through the greynir account's
# ~/Greynir -> github/Greynir symlink. pwd -P resolves that symlink, so SRC is
# always the real path (~/github/Greynir) no matter how the script is invoked,
# and the script keeps working if the checkout is renamed.
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

cd "$SRC" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
# ---------------------------------------------------------------------------
# DECOMMISSIONED 2026-08-03 -- do not re-enable without reading this.
#
# GREYNIR_DB_HOST="greynir.is" timeout 120m python scraper.py --reparse --limit=5000 \
#     || echo "!!! scraper.py --reparse exited $? (124 = killed by timeout) -- continuing"
#
# `--reparse` selects articles whose parser_version is older than the current
# one (scraper.py, iter_unparsed_articles). That makes ANY GreynirEngine
# upgrade silently enqueue the entire ~1.5M-article archive for re-parsing, at
# 5,000 a night, for months.
#
# That is not hypothetical: it is what happened here. A parser bump dated
# 2025-05-15 started a sweep on 2025-05-16 that re-extracted every pre-2023
# ruv.is article through a scraper which, after RÚV's move to Next.js, could no
# longer find the body in their old Drupal markup. It silently overwrote
# 181,712 articles with an empty body, empty tokens and no tree, and nothing
# noticed for ten months because article volume stayed normal. See PLAN.md 1.4.
#
# We do not re-parse old material on a version bump any more. Articles are
# parsed once when scraped; a re-parse is now a deliberate, scoped operation
# (scraper.py --urls <file>), not an automatic consequence of an upgrade.
# This also unblocks upgrading GreynirEngine, which would otherwise start such
# a sweep the moment it was deployed.
# ---------------------------------------------------------------------------

# The re-process stage is NOT decommissioned and must stay. processor.py
# --update selects articles where processed < parsed, so it is what gives
# entities, persons and locations to anything re-parsed by hand -- including
# the ruv.is backfill. Without it those articles have text but no extractions.
#
# A stage killed by its timeout (exit 124) must not abort the run: errexit is
# on, so that would silently skip every later stage. See the equivalent note in
# runscraper.sh.
GREYNIR_DB_HOST="greynir.is" timeout 30m python processor.py --update --limit=5000 \
    || echo "!!! processor.py --update exited $? (124 = killed by timeout) -- continuing"
deactivate
