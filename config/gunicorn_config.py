# Gunicorn configuration file for Greynir
# Works for both production and staging — derives paths from working directory

import os

DIR = os.getcwd() + "/"
proc_name = os.path.basename(os.getcwd())

bind = "unix:" + DIR + "gunicorn.sock"
worker_class = "gevent"
workers = 4
timeout = 120
# Note: preload_app is not compatible with PyPy + async workers (gevent/eventlet)
max_requests = 1000
max_requests_jitter = 50

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
