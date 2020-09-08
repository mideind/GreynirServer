## Greynir - Setup instructions for macOS

These instructions are for macOS 10.12 or later.

## Install dependencies

Using [Homebrew](https://brew.sh):

```
brew install python3 pypy3 postgresql ossp-uuid
```

Alternatively, you can install these packages manually:

* [Python 3](https://www.python.org/downloads/mac-osx/)
* [PyPy 3.5](https://pypy.org/download.html)
* [PostgreSQL](https://www.postgresql.org/download/macosx/)
* [uuid-ossp module](https://www.postgresql.org/docs/devel/uuid-ossp.html)

## Set up Python virtualenv

Make sure pip and virtualenv are up to date:

```
pip3 install --upgrade pip
pip3 install --upgrade virtualenv
```

Check out source code using [git](https://git-scm.com):

```
cd ~
git clone https://github.com/mideind/Greynir
cd ~/Greynir
```

Create and activate virtual environment, install required Python packages:

```
virtualenv -p /usr/local/bin/pypy3 venv
source venv/bin/activate
pip install -r requirements.txt
```


## Set up database

Connect to [PostgreSQL](https://www.postgresql.org) database:

```
psql
```

Create user (replace *your_name* with your username):

```
create user reynir with password 'reynir';
create user your_name;
alter role your_name with superuser;
```

Create database:

```
create database scraper with encoding 'UTF8' LC_COLLATE='is_IS.UTF-8' LC_CTYPE='is_IS.UTF-8' TEMPLATE=template0;
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

Finally, create the database tables used by Greynir (this will only create
the tables if needed, and no existing data is erased):

```
cd ~/Greynir
python scraper.py --init
```

## Run

Change to the Greynir repo directory and activate the virtual environment:

```
cd ~/Greynir
source venv/bin/activate
```

#### Web application

Defaults to running on [`localhost:5000`](http://localhost:5000) but this 
can be changed in `config/Greynir.conf`.

```
python main.py
```

#### Scrapers

```
python scraper.py
```

NB: Due to issues with Python's `fork()` in recent versions of macOS, you 
may need to run the following shell command in order for scraping to work:

```
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
```

#### Interactive shell

```
./shell.sh
```

Starts an [IPython](https://ipython.org) shell with a database session (`s`), 
the Greynir parser (`r`) and all SQLAlchemy database models preloaded. For 
more info, see [Using the Greynir Shell](shell.md).
