"""

    Greynir: Natural language processing for Icelandic

    Scraper database model

    Copyright (C) 2023 Miðeind ehf.

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

from typing import Any, Callable, Generic, Optional, Type, TypeVar, cast
from typing_extensions import Literal

from sqlalchemy import create_engine, desc, func as dbfunc
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.engine.cursor import CursorResult

from sqlalchemy.exc import SQLAlchemyError as DatabaseError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import DataError
from sqlalchemy.exc import OperationalError

from settings import Settings, ConfigError

# Which DBAPI driver SQLAlchemy should use.
#
# psycopg2 is the C implementation; psycopg2cffi is the cffi port that exists
# because psycopg2 cannot be built on PyPy. This module hardcoded the cffi port
# for as long as production ran PyPy, which cost CPython consumers speed for no
# reason.
#
# It is detected rather than pinned because two interpreters share this file.
# The web apps and the scraper pipeline are CPython 3.14 and have psycopg2. The
# topic tagger and similarity server run from vectors/venv on CPython 3.9 --
# gensim 3.8.2 imports Mapping from collections and so cannot go past 3.9 -- and
# that venv has only psycopg2cffi, installed from its own requirements.txt.
# Requiring psycopg2 here would break both of them, and one of the two is
# simserver, which costs ~16 minutes of degraded similarity to restart.
#
# Preferring rather than requiring also means the fallback disappears on its own
# when that venv is eventually retired (see PLAN.md 3.7, pgvector).
try:
    import psycopg2 as _driver  # noqa: F401

    DB_DRIVER = "psycopg2"
except ImportError:  # pragma: no cover
    import psycopg2cffi as _driver  # noqa: F401

    DB_DRIVER = "psycopg2cffi"

__all__ = (
    "DB_DRIVER",
    "create_engine",
    "desc",
    "dbfunc",
    "sessionmaker",
    "CursorResult",
    "Session",
    "DatabaseError",
    "IntegrityError",
    "DataError",
    "OperationalError",
    "ConfigError",
    "Settings",
    "GreynirDB",
    "SessionContext",
)


class GreynirDB:
    """Wrapper around the SQLAlchemy connection, engine and session"""

    def __init__(self) -> None:
        """Initialize SQLAlchemy connection to the database"""

        # Assemble the connection string. See DB_DRIVER above for why the
        # driver is detected rather than named here.
        conn_str = "postgresql+{0}://{1}:{2}@{3}:{4}/scraper".format(
            DB_DRIVER,
            Settings.DB_USERNAME,
            Settings.DB_PASSWORD,
            Settings.DB_HOSTNAME,
            Settings.DB_PORT,
        )

        # Create engine and bind session
        self._engine = create_engine(conn_str)
        self._Session: Type[Session] = cast(
            Type[Session], sessionmaker(bind=self._engine)
        )

    def create_tables(self) -> None:
        """Create all missing tables in the database"""
        from .models import Base

        Base.metadata.create_all(self._engine)  # type: ignore

    def execute(self, sql: str, **kwargs: Any) -> CursorResult:
        """Execute raw SQL directly on the engine"""
        return self._engine.execute(sql, **kwargs)  # type: ignore

    @property
    def session(self) -> Session:
        """Returns a freshly created Session instance from the sessionmaker"""
        return self._Session()


T = TypeVar("T")


class classproperty(Generic[T]):
    """A helper that creates read-only class properties"""

    def __init__(self, f: Callable[..., T]) -> None:
        self.f = f

    def __get__(self, obj: Any, owner: Any) -> T:
        return self.f(owner)


class SessionContext:
    """Context manager for database sessions"""

    # Singleton instance
    _db: Optional[GreynirDB] = None

    # pylint: disable=no-self-argument
    @classproperty
    def db(cls) -> GreynirDB:
        if cls._db is None:
            cls._db = GreynirDB()
        return cls._db

    @classmethod
    def cleanup(cls) -> None:
        """Clean up the reference to the singleton GreynirDB instance"""
        cls._db = None

    def __init__(
        self,
        session: Optional[Session] = None,
        commit: bool = False,
        read_only: bool = False,
    ) -> None:
        if session is None:
            # Create a new session that will be automatically committed
            # (if commit == True) and closed upon exit from the context
            # pylint: disable=no-member
            # Creates a new GreynirDB instance if needed
            self._session = self.db.session
            self._new_session = True
            if read_only:
                # Set the transaction as read only, which can save resources
                self._session.execute("SET TRANSACTION READ ONLY")  # type: ignore
                self._commit = True
            else:
                self._commit = commit
        else:
            self._new_session = False
            self._session = session
            self._commit = False

    def __enter__(self) -> Session:
        """Python context manager protocol"""
        # Return the wrapped database session
        return self._session

    # noinspection PyUnusedLocal
    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: BaseException,
        traceback: Any,
    ) -> Literal[False]:
        """Python context manager protocol"""
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
