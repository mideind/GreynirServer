#!/usr/bin/env bash
#
# test_local.sh
#
# Run the test suite the way CI does, against a disposable PostgreSQL cluster.
#
# The database name is hardcoded to "scraper" in db/__init__.py, so a local test
# run cannot be isolated by database name -- only by host or port. This script
# therefore spins up its own PostgreSQL cluster on a spare port, owned by the
# invoking user, and destroys it afterwards. The production cluster on 5432 is
# never touched.
#
# Usage:
#   scripts/test_local.sh                 # run the whole suite
#   scripts/test_local.sh -k test_currency  # extra args go to pytest
#
# Environment:
#   TESTDB_PORT   port for the throwaway cluster (default 5555)
#   PGBIN         PostgreSQL bin directory (default: newest under /usr/lib/postgresql)
#   KEEP_TESTDB   set to 1 to leave the cluster running for inspection

set -o errexit
set -o nounset
set -o pipefail

TESTDB_PORT="${TESTDB_PORT:-5555}"
KEEP_TESTDB="${KEEP_TESTDB:-0}"

# Refuse to go anywhere near the production cluster.
if [[ "$TESTDB_PORT" == "5432" ]]; then
    echo "ERROR: refusing to run tests against port 5432 (production)." >&2
    exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "${PGBIN:-}" ]]; then
    PGBIN="$(find /usr/lib/postgresql -maxdepth 2 -name bin -type d 2>/dev/null | sort -V | tail -1)"
fi
if [[ ! -x "$PGBIN/initdb" ]]; then
    echo "ERROR: could not find initdb. Set PGBIN to your PostgreSQL bin directory." >&2
    exit 1
fi

command -v uv >/dev/null || { echo "ERROR: uv not found on PATH." >&2; exit 1; }

PGDATA_DIR="$(mktemp -d -t greynir-testdb-XXXXXX)"

cleanup() {
    local rc=$?
    if [[ "$KEEP_TESTDB" == "1" ]]; then
        echo
        echo "KEEP_TESTDB=1: cluster left running on port $TESTDB_PORT"
        echo "  psql -h 127.0.0.1 -p $TESTDB_PORT -U postgres scraper"
        echo "  stop with: $PGBIN/pg_ctl -D $PGDATA_DIR stop"
        return $rc
    fi
    if [[ -d "$PGDATA_DIR" ]]; then
        "$PGBIN/pg_ctl" -D "$PGDATA_DIR" -m immediate stop >/dev/null 2>&1 || true
        rm -rf "$PGDATA_DIR"
    fi
    return $rc
}
trap cleanup EXIT

echo "==> Creating throwaway PostgreSQL cluster ($("$PGBIN/initdb" --version))"
"$PGBIN/initdb" -D "$PGDATA_DIR" -U postgres --encoding=UTF8 \
    --auth-local=trust --auth-host=trust >/dev/null

echo "==> Starting it on port $TESTDB_PORT"
"$PGBIN/pg_ctl" -D "$PGDATA_DIR" -l "$PGDATA_DIR/server.log" \
    -o "-p $TESTDB_PORT -h 127.0.0.1 -k $PGDATA_DIR" -w start >/dev/null

psql_test() { psql -h 127.0.0.1 -p "$TESTDB_PORT" -U postgres "$@"; }

echo "==> Setting up the scraper database (mirrors the CI steps)"
psql_test -q -c "create user reynir with password 'reynir';"
psql_test -q -c "create database scraper with encoding 'UTF8' TEMPLATE=template0;"
psql_test -q -d scraper -c "create extension if not exists \"uuid-ossp\";"
# pgvector, for articles.topic_embedding. On Debian: apt install postgresql-NN-pgvector
psql_test -q -d scraper -c "create extension if not exists vector;" || {
    echo "ERROR: could not create the pgvector extension. Install it for" >&2
    echo "your PostgreSQL version (e.g. apt install postgresql-17-pgvector)." >&2
    exit 1
}
psql_test -q -c "alter database scraper owner to reynir;"

echo "==> Writing dummy API keys (all gitignored and absent by default)"
mkdir -p resources queries/resources
cp tests/files/dummy_greynir_api_key.txt resources/GreynirServerKey.txt
cp tests/files/dummy_atm_data.json queries/resources/isb_locations.json

# icespeak asserts at import time that at least one speech engine is
# configured, so collection fails outright without these. CI writes real keys
# from repository secrets; locally we write structurally valid placeholders,
# which satisfy the import but cannot actually synthesise speech. Tests that
# call out to a TTS backend will therefore fail locally -- drop real keys into
# resources/ if you need those to pass.
if [[ ! -s resources/AWSPollyServerKey.json ]]; then
    cat > resources/AWSPollyServerKey.json <<'JSON'
{"aws_access_key_id": "dummy", "aws_secret_access_key": "dummy", "region_name": "eu-west-1"}
JSON
fi
if [[ ! -s resources/AzureSpeechServerKey.json ]]; then
    cat > resources/AzureSpeechServerKey.json <<'JSON'
{"key": "dummy", "region": "westeurope"}
JSON
fi

echo "==> Creating database tables"
GREYNIR_DB_PORT="$TESTDB_PORT" uv run scraper.py --init

echo "==> Populating test data"
psql_test -q -d scraper -f tests/files/populate_testdb.sql >/dev/null

echo "==> Running pytest against port $TESTDB_PORT"
# ICESPEAK_KEYS_DIR is not set here: utility.py points icespeak at resources/
# unconditionally, so setting it would be a no-op.
GREYNIR_DB_PORT="$TESTDB_PORT" uv run python -m pytest "$@"
