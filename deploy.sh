#! /bin/bash

# deploy.sh

# Deployment script for greynir.is

SRC=~/github/Reynir
DEST=/usr/share/nginx/greynir.is

echo "Deploying $SRC to $DEST..."

echo "Stopping greynir.is server"

sudo systemctl stop greynir

cd $DEST

echo "Upgrading the reynir package"

source p3510/bin/activate
pip install --upgrade reynir
deactivate

cd $SRC

echo "Copying files"

cp config/Adjectives.conf $DEST/config/Adjectives.conf
cp config/Index.conf $DEST/config/Index.conf
cp config/Main.conf $DEST/config/Main.conf
# Note: config/Reynir.conf is not copied
cp config/TnT-model.pickle $DEST/config/TnT-model.pickle

cp article.py $DEST/article.py
cp fetcher.py $DEST/fetcher.py
cp getimage.py $DEST/getimage.py
cp incparser.py $DEST/incparser.py
cp main.py $DEST/main.py
cp nertokenizer.py $DEST/nertokenizer.py
cp postagger.py $DEST/postagger.py
cp processor.py $DEST/processor.py
cp query.py $DEST/query.py
cp scraper.py $DEST/scraper.py
cp scraperdb.py $DEST/scraperdb.py
cp search.py $DEST/search.py
cp settings.py $DEST/settings.py
cp similar.py $DEST/similar.py
cp tnttagger.py $DEST/tnttagger.py
cp tree.py $DEST/tree.py
cp treeutil.py $DEST/treeutil.py

cp scrapers/*.py $DEST/scrapers/
cp templates/* $DEST/templates/
cp static/* $DEST/static/
cp fonts/* $DEST/fonts/

# Put a version identifier (date and time) into the about.html template
sed -i "s/\[Þróunarútgáfa\]/Útgáfa `date "+%Y-%m-%d %H:%M"`/g" $DEST/templates/about.html

echo "Deployment done"
echo "Starting greynir.is server..."

sudo systemctl start greynir
