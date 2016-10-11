#! /bin/bash
cd ~/github/Reynir
source p3/bin/activate
python scraper.py --reparse --limit=2500
python processor.py --update --limit=2600
deactivate
