#!/bin/bash
#
# This is run once every morning by cron
#
cd ~/github/Reynir
source p3510/bin/activate
timeout 120m python scraper.py --reparse --limit=5000
timeout 40m python processor.py --update --limit=10000
deactivate
