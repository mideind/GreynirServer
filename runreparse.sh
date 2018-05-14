#!/bin/bash
cd ~/github/Reynir
source p3510/bin/activate
python scraper.py --reparse --limit=5000
python processor.py --update --limit=10000
deactivate
