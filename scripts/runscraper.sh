#!/bin/bash
# Scraper
cd ~/github/Greynir
source p369/bin/activate
#timeout 20m python scraper.py --limit=2500
# Use control group to limit memory usage and swap
timeout 20m cgexec -g "memory:scraper" python scraper.py --limit=2500
deactivate
# Tagger
cd ~/github/Greynir/vectors
source venv/bin/activate
timeout 20m python builder.py --limit=2500 --notify tag
deactivate
# Processor
cd ~/github/Greynir
source p369/bin/activate
timeout 20m python processor.py --limit=3000
deactivate
