#!/usr/bin/env bash
#
# This is run once every morning by cron
# Reparses and reprocesses previously parsed articles
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
GREYNIR_DB_HOST="greynir.is" timeout 120m python scraper.py --reparse --limit=5000
GREYNIR_DB_HOST="greynir.is" timeout 30m python processor.py --update --limit=5000
deactivate
