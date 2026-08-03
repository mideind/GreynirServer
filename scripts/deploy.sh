#!/usr/bin/env bash
#
# deploy.sh
#
# Deployment script for greynir.is
#
# Prompts for confirmation before copying files over
#
# Defaults to deploying to production.
# Run with argument "staging" to deploy to staging

# set -o errexit   # Exit when a command fails
# set -o nounset   # Disallow unset variables
# set -o pipefail  # Pipeline command fails if any command fails

# Repository root, derived from this script's own location rather than a
# hardcoded path under $HOME. The old value was ~/github/Greynir, which broke
# in two ways: it depended on which user ran the script, and it did not survive
# the repository being renamed from Greynir to GreynirServer. Since errexit is
# disabled below, a wrong SRC does not abort the run -- it silently deploys
# whatever happens to be in the current directory instead.
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MODE="PRODUCTION"
DEST="/usr/share/nginx/greynir.is" # Production
SERVICE="greynir"

# Check first argument
if [[ "$1" = "staging" ]]; then
    MODE="STAGING"
    DEST="/usr/share/nginx/staging.greynir.is" # Staging
    SERVICE="staging"
fi

# Fail closed before doing anything, rather than part way through.
#
# errexit is disabled above, so a user who cannot write the deployment would
# otherwise watch every cp and pip install fail in turn while the script
# carried on regardless -- and still reach the `sudo systemctl restart` at the
# end, restarting the service after copying nothing. Deriving SRC from the
# script's own location made that reachable: the previous hardcoded
# SRC=~/github/Greynir aborted at `cd $SRC` for anyone but the deployment
# owner, which failed closed by accident rather than by design.
#
# Checking $DEST alone is not enough. On production it is group-writable
# (drwxrwxr-x greynir:greynir), so anyone in the greynir group passes, while
# the files inside -- owned by greynir, mode 0644/0755 -- do not. Test the
# things actually written instead.
if [[ ! -f "$SRC/main.py" ]]; then
    echo "Error: $SRC does not look like a Greynir checkout (no main.py)." >&2
    exit 1
fi

for target in "$DEST" "$DEST/main.py" "$DEST/config" "$DEST/scrapers"; do
    if [[ ! -e "$target" ]]; then
        echo "Error: $target does not exist. Is $DEST a deployment?" >&2
        exit 1
    fi
    if [[ ! -w "$target" ]]; then
        echo "Error: $target is not writable by $(id -un)." >&2
        echo "Run scripts/deploy.sh as the user owning the deployment (greynir)." >&2
        exit 1
    fi
done

read -rp "This will deploy Greynir to **${MODE}**. Confirm? (y/n): " CONFIRMED

if [[ "$CONFIRMED" != "y" ]]; then
    echo "Deployment aborted"
    exit 1
fi

echo "Deploying $SRC to $DEST..."

cd "$SRC" || exit 1

cp requirements.txt $DEST/requirements.txt

cd $DEST || exit 1

# echo "Upgrading dependencies according to requirements.txt"

# shellcheck disable=SC1091
source "venv/bin/activate"
pip install -r requirements.txt
deactivate

echo "Removing binary grammar files"
# Ask the venv's own interpreter where reynir lives instead of assuming
# venv/site-packages/reynir/. That path resolves ONLY on production, where
# venv/site-packages happens to be a symlink to lib/pypy3.9/site-packages.
# Staging has no such symlink, so this rm has been failing there on every
# deploy -- and because errexit is disabled at the top of this script, the
# deploy carried on and silently kept a stale compiled grammar whenever the
# grammar had changed. Deriving the path works on any venv layout and any
# interpreter, which also matters for the CPython 3.13 migration (PLAN.md 3.1),
# where the directory becomes lib/python3.13/site-packages.
#
# rm -f, not rm: a venv whose grammar has not been compiled yet is a normal
# state, not an error. The failure worth reporting is not finding reynir at all.
REYNIR_DIR="$(venv/bin/python -c 'import os, reynir; print(os.path.dirname(reynir.__file__))' 2>/dev/null)"
if [ -z "$REYNIR_DIR" ] || [ ! -d "$REYNIR_DIR" ]; then
    echo "!!! Could not locate the reynir package in $DEST/venv." >&2
    echo "!!! Refusing to continue: the app would run against a stale grammar." >&2
    exit 1
fi
rm -f "$REYNIR_DIR/Greynir.grammar.bin" "$REYNIR_DIR/Greynir.grammar.query.bin"
echo "  cleared compiled grammar in $REYNIR_DIR"

cd "$SRC" || exit 1

echo "Copying files"

cp config/Index.conf $DEST/config/Index.conf
cp config/gunicorn_config.py $DEST/gunicorn_config.py
# Note: config/Greynir.conf is not copied

# Note: .env is not copied (environment-specific)
cp article.py $DEST/article.py
cp fetcher.py $DEST/fetcher.py
cp geo.py $DEST/geo.py
cp images.py $DEST/images.py
cp main.py $DEST/main.py
cp nertokenizer.py $DEST/nertokenizer.py
cp postagger.py $DEST/postagger.py
cp processor.py $DEST/processor.py
cp scraper.py $DEST/scraper.py
cp search.py $DEST/search.py
cp settings.py $DEST/settings.py
cp similar.py $DEST/similar.py
cp tnttagger.py $DEST/tnttagger.py
cp tts.py $DEST/tts.py
cp utility.py $DEST/utility.py
cp -r db $DEST/
cp -r routes $DEST/
cp -r tree $DEST/
cp scrapers/*.py $DEST/scrapers/
cp nn/*.py $DEST/nn/

# Sync templates, static files and queries
rm -rf queries/__pycache__/
rsync -av --delete processors/ $DEST/processors/
rsync -av --delete templates/ $DEST/templates/
rsync -av --delete static/ $DEST/static/
rsync -av --delete queries/ $DEST/queries/

cp -r resources/geo $DEST/resources/

# Put a version identifier (date + commit ID) into the about.html template
ABOUT_TPL="${DEST}/templates/about.html"
sed -i "s/\[Þróunarútgáfa\]/Útgáfa $(date "+%Y-%m-%d %H:%M")/g" "${ABOUT_TPL}"
GITVERS=$(git rev-parse HEAD) # Get git commit ID
GITVERS=${GITVERS:0:7} # Truncate it
sed -i "s/\[Git-útgáfa\]/${GITVERS}/g" "${ABOUT_TPL}"

echo "Restarting gunicorn server..."
sudo systemctl restart $SERVICE

if [[ "$MODE" = "PRODUCTION" ]]; then
    echo "Updating similarity server dependencies..."
    # shellcheck disable=SC1091
    source "$SRC/vectors/venv/bin/activate"
    pip install -r "$SRC/vectors/requirements.txt"
    deactivate
    # Note: similarity server is NOT restarted here (13 min downtime).
    # Restart it manually if needed: sudo systemctl restart similarity
fi

echo "Deployment done"
