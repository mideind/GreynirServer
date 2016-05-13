#! /bin/bash
cd ~/github/Reynir
source p3/bin/activate
python scraper.py --limit=2000
python processor.py --limit=2000
deactivate
