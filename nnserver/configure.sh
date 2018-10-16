#!/usr/bin/env bash

# Small hack to make python imports easier without major refactoring

SCRIPT_NAME=$(basename $0)
SCRIPT_PATH=$(readlink -f $0)
SCRIPT_DIR=$(dirname $SCRIPT_PATH)

PROJECT_DIR=$(dirname $SCRIPT_DIR)
PROJECT_LINK=$SCRIPT_DIR/greynir

if [ ! -d "$PROJECT_LINK" ]; then
    echo "Making symbolic link to project directory"
    echo "Remember to install nnserver/requirements.txt with pip"
    ln -s "$PROJECT_DIR" "$PROJECT_LINK"
fi
