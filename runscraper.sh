#! /bin/bash
cd ~/github/Reynir
source p3/bin/activate
python scraper.py --limit=500
deactivate
