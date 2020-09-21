# Gunicorn configuration file for greynir.is

DIR = "/usr/share/nginx/greynir.is/"

bind = "unix:" + DIR + "gunicorn.sock"
worker_class = "eventlet"
workers = 3
threads = 2
timeout = 120

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
