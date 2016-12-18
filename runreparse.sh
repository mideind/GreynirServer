#!/bin/bash
cd /home/villi/github/Reynir
source p33/bin/activate
python scraper.py --reparse --limit=2500
python processor.py --update --limit=2600
deactivate
