#!/bin/bash
cd ~/github/Reynir
source p358/bin/activate
python scraper.py --reparse --limit=2500
python processor.py --update --limit=3100
deactivate
