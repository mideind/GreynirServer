#!/usr/bin/env bash
#
# Run topic vector tagging program
#

# Repository root, derived from this script's own location rather than the
# hardcoded ~/github/Greynir, which depended on both the user running the
# script and the checkout's directory name. pwd -P resolves any symlink, so
# SRC is always the real path and this survives a rename of the checkout.
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

# Tagger
cd "$SRC/vectors" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python builder.py --limit=2500 --notify tag
deactivate
