"""

    Greynir: Natural language processing for Icelandic

    Scraper database model

    Copyright (C) 2020 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.


    This module contains database-related functionality.

"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from settings import Settings, ConfigError

from sqlalchemy.exc import SQLAlchemyError as DatabaseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import DataError
from sqlalchemy.exc import OperationalError
from sqlalchemy import desc
from sqlalchemy import func as dbfunc

from .models import Base


class Scraper_DB:
    """ Wrapper around the SQLAlchemy connection, engine and session """

    def __init__(self):
        """ Initialize the SQLAlchemy connection to the scraper database """

        # Assemble the connection string, using psycopg2cffi which
        # supports both PyPy and CPython
        conn_str = "postgresql+{0}://reynir:reynir@{1}:{2}/scraper".format(
            "psycopg2cffi",
            Settings.DB_HOSTNAME,
            Settings.DB_PORT,
        )

        # Create engine and bind session
        self._engine = create_engine(conn_str)
        self._Session = sessionmaker(bind=self._engine)

    def create_tables(self):
        """ Create all missing tables in the database """
        Base.metadata.create_all(self._engine)

    def execute(self, sql, **kwargs):
        """ Execute raw SQL directly on the engine """
        return self._engine.execute(sql, **kwargs)

    @property
    def session(self):
        """ Returns a freshly created Session instance from the sessionmaker """
        return self._Session()


class classproperty:

    def __init__(self, f):
        self.f = f

    def __get__(self, obj, owner):
        return self.f(owner)


class SessionContext:
    """ Context manager for database sessions """

    _db = None  # Singleton instance of Scraper_DB

    # pylint: disable=no-self-argument
    @classproperty
    def db(cls):
        if cls._db is None:
            cls._db = Scraper_DB()
        return cls._db

    @classmethod
    def cleanup(cls):
        """ Clean up the reference to the singleton Scraper_DB instance """
        cls._db = None

    def __init__(self, session=None, commit=False, read_only=False):

        if session is None:
            # Create a new session that will be automatically committed
            # (if commit == True) and closed upon exit from the context
            # pylint: disable=no-member
            self._session = self.db.session  # Creates a new Scraper_DB instance if needed
            self._new_session = True
            if read_only:
                # Set the transaction as read only, which can save resources
                self._session.execute("SET TRANSACTION READ ONLY")
                self._commit = True
            else:
                self._commit = commit
        else:
            self._new_session = False
            self._session = session
            self._commit = False

    def __enter__(self):
        """ Python context manager protocol """
        # Return the wrapped database session
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(self, exc_type, exc_value, traceback):
        """ Python context manager protocol """
        if self._new_session:
            if self._commit:
                if exc_type is None:
                    # No exception: commit if requested
                    self._session.commit()
                else:
                    self._session.rollback()
            self._session.close()
        # Return False to re-throw exception from the context, if any
        return False
