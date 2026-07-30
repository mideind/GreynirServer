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

# Scraper
cd "$SRC" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python scraper.py --limit=2500
# Use control group to limit memory usage and swap
#GREYNIR_DB_HOST="greynir.is" timeout 20m cgexec -g "memory:scraper" python scraper.py --limit=2500
deactivate

# Processor
cd "$SRC" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python processor.py --limit=3000
deactivate
