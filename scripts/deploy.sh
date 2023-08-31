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

set -o errexit   # Exit when a command fails
# set -o nounset   # Disallow unset variables
set -o pipefail  # Pipeline command fails if any command fails

SRC=~/github/Greynir
MODE="PRODUCTION"
DEST="/usr/share/nginx/greynir.is" # Production
SERVICE="greynir"

# Check first argument
if [[ "$1" = "staging" ]]; then
    MODE="STAGING"
    DEST="/usr/share/nginx/staging" # Staging
    SERVICE="staging"
fi

read -rp "This will deploy Greynir to **${MODE}**. Confirm? (y/n): " CONFIRMED

if [[ "$CONFIRMED" != "y" ]]; then
    echo "Deployment aborted"
    exit 1
fi

echo "Deploying $SRC to $DEST..."

cd $SRC || exit 1

cp requirements.txt $DEST/requirements.txt

cd $DEST || exit 1

# echo "Upgrading dependencies according to requirements.txt"

# shellcheck disable=SC1091
source "venv/bin/activate"
pip install --upgrade -r requirements.txt
deactivate

echo "Removing binary grammar files"
rm venv/site-packages/reynir/Greynir.grammar.bin
rm venv/site-packages/reynir/Greynir.grammar.query.bin

cd $SRC || exit 1

echo "Copying files"

cp config/Index.conf $DEST/config/Index.conf
# Note: config/Greynir.conf is not copied

cp .env $DEST/.env
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
cp speak.py $DEST/speak.py
cp tnttagger.py $DEST/tnttagger.py
cp tree.py $DEST/tree.py
cp treeutil.py $DEST/treeutil.py
cp utility.py $DEST/utility.py
cp -r db $DEST/
cp -r routes $DEST/
cp -r speech $DEST/
cp scrapers/*.py $DEST/scrapers/
cp nn/*.py $DEST/nn/

# Sync templates, static files and queries
rm -rf queries/__pycache__/
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

echo "Reloading gunicorn server..."

sudo systemctl reload $SERVICE

echo "Deployment done"
