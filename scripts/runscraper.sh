#!/bin/bash

# Scraper
cd ~/Greynir || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python scraper.py --limit=2500
# Use control group to limit memory usage and swap
#GREYNIR_DB_HOST="greynir.is" timeout 20m cgexec -g "memory:scraper" python scraper.py --limit=2500
deactivate

# Processor
cd ~/Greynir || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python processor.py --limit=3000
deactivate
