#!/bin/sh
#
# Start IPython shell using config stored in repository
#

if [ -z "$VIRTUAL_ENV" ]; then
	echo "Not running in a virtualenv"
  	exit
fi

VENV_DIR="`basename \"$VIRTUAL_ENV\"`"

if [ ! -d "$VENV_DIR" ]; then
	echo "virtualenv directory '${VENV_DIR}' not found"
	exit
fi

IPYTHON_BIN="${VENV_DIR}/bin/ipython3"

if [ ! -e "$IPYTHON_BIN" ]; then
	echo "IPython binary not found: '${IPYTHON_BIN}'"
	exit
fi

IPYTHON_CONFIG=".ipython.py"

$IPYTHON_BIN --config=$IPYTHON_CONFIG --pprint --no-simple-prompt
