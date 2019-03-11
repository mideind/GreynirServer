#!/bin/sh
#
# Start IPython shell using config stored in repository
#

# Change to parent directory of the directory containing the script
# This should be the repo root
SCRIPT_DIR=$(dirname "$0")
CONFIG_PATH="${SCRIPT_DIR}/.ipython.py"

if [ ! -e $CONFIG_PATH ]; then
    echo "Warning: IPython config not found at ${CONFIG_PATH}"
fi

cd $SCRIPT_DIR/..

# Make sure we're running in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
	echo "Not running in a virtualenv"
  	exit
fi

VENV_DIR="`basename \"$VIRTUAL_ENV\"`"

if [ ! -d "$VENV_DIR" ]; then
	echo "virtualenv directory '${VENV_DIR}' not found"
	exit
fi

# Check for presence of IPython binary
IPYTHON_BIN="${VENV_DIR}/bin/ipython3"

if [ ! -e "$IPYTHON_BIN" ]; then
	echo "IPython binary not found: '${IPYTHON_BIN}'"
	exit
fi

# Run IPython shell iwth custom configuration
$IPYTHON_BIN --config="${CONFIG_PATH}" --pprint --no-simple-prompt
