#!/usr/bin/env bash
#
# Run topic vector tagging program
#
# topictagger.py runs in the pipeline's own environment (venv, CPython 3.14)
# from the repository root, like processor.py. It replaces vectors/builder.py,
# which needed gensim 3.8 and therefore a CPython 3.9 venv of its own; that
# venv is kept only for rebuilding the LSI model and as the rollback below.
#
# It needs the exported LSI model in resources/lsi/, which is gitignored and
# deployed out-of-band (see topicvector.py). Without it the tagger exits 1
# instead of tagging nothing, and the health check's topic-embedding check
# alerts within a few hours.
#
# Rollback, if ever needed: the old tagger still works against the same
# database and topics table, so this line from before the switch restores it:
#   cd "$SRC/vectors" && source venv/bin/activate && \
#   GREYNIR_DB_HOST="greynir.is" timeout 20m python builder.py --limit=2500 tag

# Repository root, derived from this script's own location rather than the
# hardcoded ~/github/Greynir, which depended on both the user running the
# script and the checkout's directory name. pwd -P resolves any symlink, so
# SRC is always the real path and this survives a rename of the checkout.
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

cd "$SRC" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate
GREYNIR_DB_HOST="greynir.is" timeout 20m python topictagger.py --limit=2500 tag \
    || echo "!!! topictagger.py exited $? (124 = killed by timeout)"
deactivate
