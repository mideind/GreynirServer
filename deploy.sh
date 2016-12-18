#! /bin/bash

# deploy.sh

# Deployment script for greynir.is

SRC=~/github/Reynir
DEST=/usr/share/nginx/greynir.is

echo "Deploying $SRC to $DEST..."

cd $SRC

echo "Stopping greynir.is server..."

sudo systemctl stop greynir

cp config/Abbrev.conf $DEST/config/Abbrev.conf
cp config/Adjectives.conf $DEST/config/Adjectives.conf
cp config/Main.conf $DEST/config/Main.conf
cp config/Prefs.conf $DEST/config/Prefs.conf
cp config/Verbs.conf $DEST/config/Verbs.conf
cp config/VerbPrepositions.conf $DEST/config/VerbPrepositions.conf

cp article.py $DEST/article.py
cp baseparser.py $DEST/baseparser.py
cp bindb.py $DEST/bindb.py
cp binparser.py $DEST/binparser.py
cp dawgdictionary.py $DEST/dawgdictionary.py
cp fastparser.py $DEST/fastparser.py
cp fetcher.py $DEST/fetcher.py
cp getimage.py $DEST/getimage.py
cp glock.py $DEST/glock.py
cp grammar.py $DEST/grammar.py
cp incparser.py $DEST/incparser.py
cp libeparser.so $DEST/libeparser.so
cp main.py $DEST/main.py
cp processor.py $DEST/processor.py
cp query.py $DEST/query.py
cp reducer.py $DEST/reducer.py
cp Reynir.grammar $DEST/Reynir.grammar
cp scraperdb.py $DEST/scraperdb.py
cp scraper.py $DEST/scraper.py
cp settings.py $DEST/settings.py
cp tokenizer.py $DEST/tokenizer.py
cp tree.py $DEST/tree.py

cp resources/ordalisti.dawg.pickle $DEST/resources/

cp scrapers/*.py $DEST/scrapers/
cp templates/* $DEST/templates/
cp static/* $DEST/static/
cp fonts/* $DEST/fonts/

echo "Deployment done"
echo "Starting greynir.is server..."

sudo systemctl start greynir
