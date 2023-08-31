#!/usr/bin/env bash

# Delete all text-to-speech audio scratch files older than 1 day (24 hours)
find /usr/share/nginx/greynir.is/static/audio/tmp/* -mtime +1 -exec rm {} \;
