#!/bin/sh
#
# Purge all logged queries older than 30 days
#

psql -h 127.0.0.1 -U reynir -d scraper -c \
"DELETE FROM queries WHERE timestamp < NOW() - INTERVAL '30 days';"


