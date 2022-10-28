#!/usr/bin/env bash
#
# This is run once every morning by cron
# Reparses and reprocesses previously parsed articles
#

set -o errexit   # Exit when a command fails
set -o nounset   # Disallow unset variables
set -o pipefail  # Pipeline command fails if any command fails

cd ~/Greynir || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 120m python scraper.py --reparse --limit=5000
GREYNIR_DB_HOST="greynir.is" timeout 30m python processor.py --update --limit=5000
deactivate
