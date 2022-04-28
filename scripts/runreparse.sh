#!/bin/bash
#
# This is run once every morning by cron
#
cd ~/Greynir || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 120m python scraper.py --reparse --limit=5000
GREYNIR_DB_HOST="greynir.is" timeout 30m python processor.py --update --limit=5000
deactivate
