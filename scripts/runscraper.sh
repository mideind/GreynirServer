#!/bin/bash
# Scraper
cd ~/github/Reynir
source p3510/bin/activate
timeout 20m python scraper.py --limit=2500
deactivate
# Tagger
cd ~/github/Reynir/vectors
source venv/bin/activate
timeout 20m python builder.py --limit=2500 --notify tag
deactivate
# Processor
cd ~/github/Reynir
source p3510/bin/activate
timeout 20m python processor.py --limit=3000
deactivate
