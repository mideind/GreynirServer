#!/usr/bin/env bash

# Delete all STT audio scratch files older than 24 hours
find /usr/share/nginx/greynir.is/static/audio/tmp/* -mtime +1 -exec rm {} \;
