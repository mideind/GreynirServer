FROM postgres:latest
MAINTAINER Jón Levy <nonni@nonni.cc>
# create the image: docker build -t postgres:greynir . 
# run a container: docker run postgres:greynir -e POSTGRES_PASSWORD=1234 -d postgres

# Set the locale
RUN locale-gen is_IS.UTF-8  

COPY ./default_locale /etc/default/locale
RUN chmod 0755 /etc/default/locale

ENV LANG is_IS.UTF-8  
ENV LANGUAGE is_IS:en  
ENV LC_ALL is_IS.UTF-8  

ADD docker-scripts/init.sql /docker-entrypoint-initdb.d/init.sql
