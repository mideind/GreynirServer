#! /bin/bash

# deploy.sh

# Deployment script for greynir.is

SRC=/home/villi/github/Reynir
DEST=/usr/share/nginx/greynir.is

echo Deploying $SRC to $DEST...

cd $SRC

echo Stopping greynir.is server...

sudo systemctl stop greynir

cp Abbrev.conf $DEST/Abbrev.conf
cp Adjectives.conf $DEST/Adjectives.conf
cp baseparser.py $DEST/baseparser.py
cp bindb.py $DEST/bindb.py
cp binparser.py $DEST/binparser.py
cp dawgdictionary.py $DEST/dawgdictionary.py
cp fastparser.py $DEST/fastparser.py
cp favicon.ico $DEST/favicon.ico
cp getimage.py $DEST/getimage.py
cp glock.py $DEST/glock.py
cp grammar.py $DEST/grammar.py
cp libeparser.so $DEST/libeparser.so
cp Main.conf $DEST/Main.conf
cp main.py $DEST/main.py
cp Prefs.conf $DEST/Prefs.conf
cp processor.py $DEST/processor.py
cp ptest.py $DEST/ptest.py
cp query.py $DEST/query.py
cp reducer.py $DEST/reducer.py
cp Reynir.grammar $DEST/Reynir.grammar
cp scraperdb.py $DEST/scraperdb.py
cp scraper.py $DEST/scraper.py
cp settings.py $DEST/settings.py
cp tokenizer.py $DEST/tokenizer.py
cp tree.py $DEST/tree.py
cp Verbs.conf $DEST/Verbs.conf

cp resources/ordalisti.dawg.pickle $DEST/resources/

cp scrapers/*.py $DEST/scrapers/
cp templates/* $DEST/templates/
cp static/* $DEST/static/
cp fonts/* $DEST/fonts/

echo Deployment done
echo Starting greynir.is server...

sudo systemctl start greynir
