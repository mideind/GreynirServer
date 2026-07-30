#!/usr/bin/env bash
#
# Run scraper and processor programs
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

# A stage that fails must not abort the script. errexit is on, so a stage
# killed by its timeout (exit 124) used to abort the run before the later
# stages, silently: no error, no log line, nothing to distinguish it from a
# normal run. Measured 2026-07-30 while the dv.is reparse backlog was draining
# -- 41 scrape runs, only 37 of which reached the processor, four consecutive
# misses. Articles were parsed and then never processed, with nothing saying
# so. Report the failure and carry on to the next stage instead.

# Scraper
cd "$SRC" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python scraper.py --limit=2500 \
    || echo "!!! scraper.py exited $? (124 = killed by timeout) -- continuing"
# Use control group to limit memory usage and swap
#GREYNIR_DB_HOST="greynir.is" timeout 20m cgexec -g "memory:scraper" python scraper.py --limit=2500
deactivate

# Processor
cd "$SRC" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python processor.py --limit=3000 \
    || echo "!!! processor.py exited $? (124 = killed by timeout) -- continuing"
deactivate
