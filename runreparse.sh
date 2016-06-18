#! /bin/bash
cd ~/github/Reynir
source p3/bin/activate
python scraper.py --reparse --limit=2000
python processor.py --update --limit=2100
deactivate
