#! /bin/bash

# Shell script to start Gunicorn running Reynir (www.greynir.is)

cd /usr/share/nginx/greynir.is
source p3510/bin/activate
gunicorn -c gunicorn_config.py main:app
deactivate
