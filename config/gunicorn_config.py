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
# Raised 2026-08-02, from 1000/50. At the old ceiling a worker recycled every
# ~5 minutes under production load, which is pure overhead: there is no leak to
# guard against. Staging workers sit at ~200 MB after 19 hours without
# recycling, and production RSS fluctuates in a 440-535 MB band with no
# relation to worker age. The daily 05:05 restart bounds worker lifetime
# anyway, so this is only a backstop.
#
# The jitter matters as much as the ceiling: at 50 on 1000, four equally loaded
# workers recycled almost in lockstep.
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
