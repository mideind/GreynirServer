#!/bin/bash
#
# This is run once every morning by cron
#
cd ~/Greynir
source p369/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 120m python scraper.py --reparse --limit=5000
GREYNIR_DB_HOST="greynir.is" timeout 40m python processor.py --update --limit=10000
deactivate
