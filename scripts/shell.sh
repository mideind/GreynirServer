#!/bin/sh
#
# Start IPython shell using config stored in repository
#

command -v ipython >/dev/null 2>&1 || \
{ echo >&2 "Requires IPython. Run 'pip install ipython'."; exit 1; }


SCRIPT_DIR=$(dirname "$0")
CONFIG_PATH="${SCRIPT_DIR}/.ipython.py"

if [ ! -e "$CONFIG_PATH" ]; then
    echo "Warning: IPython config not found at ${CONFIG_PATH}"
fi

# Change to parent directory of the script
# This should be the repo root
cd "$SCRIPT_DIR/.." || exit 1

# Make sure we're running in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
	echo "Not running in a virtualenv"
  	exit
fi

VENV_DIR="$(basename "$VIRTUAL_ENV")"

if [ ! -d "$VENV_DIR" ]; then
	echo "virtualenv directory '${VENV_DIR}' not found"
	exit
fi

# Run IPython shell with custom configuration
ipython --config="${CONFIG_PATH}" --pprint --no-simple-prompt
