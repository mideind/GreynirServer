#!/bin/bash
#
# This is run once every morning by cron
#
cd ~/Greynir || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 120m python scraper.py --reparse --limit=7500
GREYNIR_DB_HOST="greynir.is" timeout 40m python processor.py --update --limit=10000
deactivate
