#! /bin/bash
# Scraper
cd ~/github/Reynir
source p3/bin/activate
python scraper.py --limit=2000
deactivate
# Tagger
cd ~/github/Reynir/vectors
source venv/bin/activate
python builder.py --limit=2000 tag
deactivate
# Processor
cd ~/github/Reynir
source p3/bin/activate
python processor.py --limit=2000
deactivate
