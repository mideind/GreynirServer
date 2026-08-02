# Gunicorn configuration file for Greynir
# Works for both production and staging — derives paths from working directory

import os

DIR = os.getcwd() + "/"
proc_name = os.path.basename(os.getcwd())

bind = "unix:" + DIR + "gunicorn.sock"
worker_class = "gevent"
workers = 2 if "staging" in proc_name else 4
timeout = 120
# Note: preload_app is not compatible with PyPy + async workers (gevent/eventlet)
# Recycling a gevent worker drops the connections nginx has already handed to
# the socket backlog. nginx retries idempotent requests, so GETs recover, but
# POSTs surface to the client as a 502. At 1000/50 each worker recycled about
# every 16 minutes under production load, which cost ~700 502s an hour on
# POST /similar and POST /summary.api — 4.7% of all requests.
#
# Raised 2026-08-02. There is no leak to guard against: staging workers sit at
# ~200 MB after 19 hours without recycling, and production RSS fluctuates in a
# 440-535 MB band with no relation to worker age. The daily 05:05 restart
# bounds worker lifetime anyway; this is only a backstop.
max_requests = 20000
max_requests_jitter = 2000

# Read user and group name from text config file
with open(DIR + "gunicorn_user.txt") as f:
    user = f.readline().strip()
    group = f.readline().strip()

pidfile = DIR + "gunicorn.pid"

# Remove the Greynir.grammar.bin file to ensure that
# the grammar will be reparsed and a fresh copy generated
try:
    os.remove(DIR + "Greynir.grammar.bin")
except OSError:
    # File probably didn't exist
    pass
