# Gunicorn configuration file for greynir.is

DIR = "/usr/share/nginx/greynir.is/"

proc_name = "greynir.is"
bind = "unix:" + DIR + "gunicorn.sock"
worker_class = "eventlet"
workers = 4
threads = 2
timeout = 120
# Note: preload_app is not compatible with eventlet on PyPy
max_requests = 1000
max_requests_jitter = 50

# Read user and group name from text config file
with open(DIR + "gunicorn_user.txt") as f:
    user = f.readline().strip()
    group = f.readline().strip()

pidfile = DIR + "gunicorn.pid"

# Remove the Greynir.grammar.bin file to ensure that
# the grammar will be reparsed and a fresh copy generated

import os

try:
    os.remove(DIR + "Greynir.grammar.bin")
except OSError:
    # File probably didn't exist
    pass
