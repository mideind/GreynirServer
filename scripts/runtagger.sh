#!/bin/bash

# Tagger
cd ~/github/Greynir/vectors || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python builder.py --limit=2500 --notify tag
deactivate
