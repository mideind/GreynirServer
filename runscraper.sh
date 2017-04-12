#!/bin/bash
# Scraper
cd ~/github/Reynir
source p35/bin/activate
python scraper.py --limit=2500
deactivate
# Tagger
cd ~/github/Reynir/vectors
source venv/bin/activate
python builder.py --limit=2500 --notify tag
deactivate
# Processor
cd ~/github/Reynir
source p35/bin/activate
python processor.py --limit=3000
#python processor.py --update --limit=3000
deactivate
