# Greynir - Setup instructions for GNU/Linux (Debian/Ubuntu)

The following instructions assume you are running a reasonably modern
version of Debian or Ubuntu and have `sudo` access.

## Locale

Set up Icelandic locale `is_IS.utf8`:

##### Debian

```bash
sudo dpkg-reconfigure locales
```

##### Ubuntu

```bash
sudo locale-gen is_IS.UTF-8
sudo update-locale
```

NB: If PostgreSQL is already running on your machine, it needs to be restarted:

```bash
sudo systemctl restart postgresql
```

See below for instructions on installing PostgreSQL client libraries.

## Set up Python virtualenv

Install Python 3 and other packages required by Greynir:

```bash
sudo apt-get install python3
sudo apt-get install libgeos-dev libpq-dev
```

Make sure you have the latest version of `pip` and `virtualenv`.

```bash
sudo -H pip3 install --upgrade pip
pip3 install --upgrade virtualenv
```

Install [git](https://git-scm.com) if it's not already installed:

```bash
sudo apt-get install git
```

Install PyPy 3.9 or later ([available here](http://pypy.org/download.html)).
For example:

```bash
mkdir ~/pypy
cd ~/pypy
wget https://downloads.python.org/pypy/pypy3.9-v7.3.12-linux64.tar.bz2
tar --strip-components=1 -xvf pypy3.9-v7.3.12-linux64.tar.bz2
```

The PyPy binary should now be installed in `~/pypy/bin/pypy3`.

Speaking of PyPy, if you try to run Greynir and get an error message saying that
the library `libgeos_c.so` cannot be loaded, you may need a symlink from your
`pypy/lib` directory to the `libgeos_c.so` file. Something like this:

```bash
cd ~/pypy/lib
ln -s /usr/lib/x86_64-linux-gnu/libgeos_c.so .
```

Now, check out the Greynir repo:

```bash
cd ~
git clone https://github.com/mideind/Greynir
cd ~/Greynir
```

Create and activate virtual environment, install required Python packages:

```bash
virtualenv -p ~/pypy/bin/pypy3 venv
source venv/bin/activate
pip install -r requirements.txt
```

## Set up database

### Install PostgreSQL

Install PostgreSQL 9.5 or later. For example:

```bash
sudo apt-get install postgresql-contrib postgresql-client libpq-dev
```

Permit user access to PostgreSQL from localhost by editing `pg_hba.conf`
(replace `9.5` in the path with your version of PostgreSQL):

```bash
sudo nano /etc/postgresql/9.5/main/pg_hba.conf
```

Make sure that the config file contains the following entries:

```text
# IPv4 local connections:
host    all       all             127.0.0.1/32      trust
# IPv6 local connections:
host    all       all             ::1/128           trust
```

Restart PostgreSQL for the changes to take effect:

```bash
sudo systemctl reload postgresql
```

### Set up users

Change to the default PostgreSQL user `postgres`:

```bash
sudo su - postgres
```

Launch PostgreSQL client and create database users
(replace *your_user_name* with your username):

```bash
psql
create user reynir with password 'reynir';
create user your_user_name;
alter role your_user_name with superuser;
```

### Create database

```postgresql
create database scraper with encoding 'UTF8' LC_COLLATE='is_IS.UTF-8' LC_CTYPE='is_IS.UTF-8' TEMPLATE=template0;
```

Alter the database owner to be the user `reynir`
(fixes the permissions for PostgreSQL 15+):

```postgresql
alter database scraper owner to reynir;
```

Enable uuid extension:

```postgresql
\c scraper
create extension if not exists "uuid-ossp";
```

Verify that the uuid extension is enabled:

```postgresql
select * from pg_extension;
```

and then `\q` to quit the `psql` client.

Finally, create the database tables used by Greynir (this will only create
the tables if needed, and no existing data is erased):

```bash
cd ~/Greynir
python scraper.py --init
```

## Run

Change to the Greynir repository and activate the virtual environment:

```bash
cd ~/Greynir
source venv/bin/activate
```

You should now be able to run Greynir.

##### Web application

```bash
python main.py
```

Defaults to running on [`localhost:5000`](http://localhost:5000) but this
can be changed in `config/Greynir.conf`.

##### Scrapers

```bash
python scraper.py
```

##### Interactive shell

```bash
./shell.sh
```

Starts an [IPython](https://ipython.org) shell with a database session (`s`),
the Greynir parser (`r`) and all SQLAlchemy database models preloaded. For more
info, see [Using the Greynir Shell](shell.md).
