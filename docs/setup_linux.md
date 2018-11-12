# Greynir - Setup instructions for GNU/Linux (Debian/Ubuntu)

The following instructions assume you are running a reasonably modern version of Debian or Ubuntu.

## Locale

Set up Icelandic locale (`is_IS.utf8`):

##### Debian

```
sudo dpkg-reconfigure locales
```

##### Ubuntu

```
sudo locale-gen is_IS.UTF-8
sudo update-locale
```

NB: If a PostgreSQL database is already running, it needs to be restarted after the locale change:

```
sudo systemctl restart postgresql
```

## Set up Python virtualenv

Make sure you have the latest version of pip and virtualenv.

```
sudo -H pip install --upgrade pip
pip install --upgrade virtualenv
```

Install git if not already installed:

```
sudo apt-get install git
```

Install PyPy3.5 or later ([available here](http://pypy.org/download.html)).

```
mkdir ~/pypy
cd ~/pypy
wget wget https://bitbucket.org/pypy/pypy/downloads/pypy3-v6.0.0-linux64.tar.bz2
tar --strip-components=1 -xvf pypy3-v6.0.0-linux64.tar.bz2
```

At this point, the `pypy` binary is installed in `~/pypy/bin/pypy3`.

Check out the Greynir repo:

```
cd ~
git clone https://github.com/vthorsteinsson/Reynir
cd ~/Reynir
```

Create and activate virtual environment, install required Python packages:

```
$ virtualenv -p /usr/local/bin/pypy3 venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt
```

## Set up database

### Install postgres

Install PostgreSQL version 9.5 or later (Greynir relies on the UPSERT feature, only available in 9.5+).

```
sudo apt-get install postgresql-contrib libpq-dev 
sudo apt-get install postgresql-client libpq-dev
```

Stilla þarf notendaaðgang þannig að (a) allur aðgangur sé leyfður frá sömu tölvu (breyta má þessu ef rýmri eða þrengri aðgangs er þörf), eða (b) gagnagrunnsþjónn leyfi aðgang frá biðlaratölvu (client).

```
sudo nano /etc/postgresql/9.5/main/pg_hba.conf
# IPv4 local connections:
host    all       all             127.0.0.1/32      trust
# IPv6 local connections:
host    all       all             ::1/128           trust
```

Ef pg_hba.conf er breytt þarf að segja PostgreSQL að lesa inn nýja uppsetningu:

```
sudo systemctl reload postgresql
```
### Set up users

Change to user `postgres`:

```
sudo su - postgres
```

Launch postgres client and create users (replace *your_name* with your username):

```
create user reynir with password 'reynir';
create user your_name;
alter role your_name with superuser;
```

### Create database

```
create database scraper with encoding 'UTF8' \ 
LC_COLLATE='is_IS.utf8' LC_CTYPE='is_IS.utf8' \ 
TEMPLATE=template0;
```

Enable uuid extension:

```
\c scraper
create extension if not exists "uuid-ossp";
```

Verify that the uuid extension is enabled:

```
select * from pg_extension;
```

and then `\q` to quit the postgres client.

Finally, create the database tables used by Greynir:

```
cd ~/Reynir
pypy3 scraper.py --init
```

## Run

Change to the Reynir repo directory and activate virtual environment:

```
cd ~/Reynir
venv/bin/activate
```

#### Web application

Defaults to running on [`localhost:5000`](http://localhost:5000) but this can be changed in `config/Reynir.conf`.

```
python main.py
```

#### Scrapers

```
python scraper.py
```

#### Interactive shell

Start an [IPython](https://ipython.org) shell with a database session (`s`), the Reynir parser (`r`) and all SQLAlchemy database models preloaded (see `scraperdb.py`):

```
./shell.sh
```
