FROM postgres:latest
MAINTAINER Jón Levy <nonni@nonni.cc>
# create the image: docker build -t postgres:greynir . 
# run a container: docker run postgres:greynir -e POSTGRES_PASSWORD=1234 -d postgres

# Set the locale
RUN localedef -i is_IS -c -f UTF-8 -A /usr/share/locale/locale.alias is_IS.UTF-8

ENV LANG is_IS.utf8

ADD resources/ord.csv /srv/ord.csv
ADD docker-scripts/init.sql /docker-entrypoint-initdb.d/init.sql
