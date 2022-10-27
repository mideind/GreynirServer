#!/usr/bin/env bash
#
# Purge all logged queries in queries table older than 30 days
#

psql -h "greynir.is" -U reynir -d scraper -c \
"DELETE FROM queries WHERE timestamp < NOW() - INTERVAL '30 days';"
