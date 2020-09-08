#!/bin/sh
#
# Purge all logged queries older than 30 days
#

psql -h "greynir.is" -U reynir -d scraper -c \
"DELETE FROM queries WHERE timestamp < NOW() - INTERVAL '30 days';"
