#!/bin/bash

# Tagger
cd ~/Greynir/vectors
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python builder.py --limit=2500 --notify tag
deactivate
