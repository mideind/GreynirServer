"""
    Greynir: Natural language processing for Icelandic

    Settings module

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


    This module reads and interprets the Greynir.conf configuration file.
    The file can include other files using the $include directive,
    making it easier to arrange configuration sections into logical
    and manageable pieces.

    Sections are identified like so: [ section_name ]

    Comments start with # signs.

    Sections are interpreted by section handlers.

"""

from typing import Set, Tuple, Union

import os
import threading

from reynir.basics import ConfigError, LineReader

# Do not remove, relied on by other modules who import changedlocale via settings
from reynir.basics import changedlocale


class NoIndexWords:
    """Wrapper around set of word stems and categories that should
    not be indexed"""

    SET: Set[Tuple[str, str]] = set()
    _cat = "so"  # Default category

    # The word categories that are indexed in the words table
    CATEGORIES_TO_INDEX = frozenset(
        ("kk", "kvk", "hk", "person_kk", "person_kvk", "entity", "lo", "so")
    )

    @staticmethod
    def set_cat(cat: str) -> None:
        """Set the category for the following word stems"""
        NoIndexWords._cat = cat

    @staticmethod
    def add(stem: str) -> None:
        """Add a word stem and its category. Called from the config file handler."""
        NoIndexWords.SET.add((stem, NoIndexWords._cat))


class Settings:
    """Global settings"""

    _lock = threading.Lock()
    loaded = False

    # Postgres SQL database server hostname and port
    DB_HOSTNAME = os.environ.get("GREYNIR_DB_HOST", "localhost")
    DB_PORT_STR = os.environ.get("GREYNIR_DB_PORT", "5432")  # Default PostgreSQL port
    DB_USERNAME = os.environ.get("GREYNIR_DB_USERNAME", "reynir")
    DB_PASSWORD = os.environ.get("GREYNIR_DB_PASSWORD", "reynir")

    try:
        DB_PORT = int(DB_PORT_STR)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: DB_PORT={0}".format(DB_PORT_STR)
        )

    # Flask server host and port
    HOST = os.environ.get("GREYNIR_HOST", "localhost")
    PORT_STR = os.environ.get("GREYNIR_PORT", "5000")
    try:
        PORT = int(PORT_STR)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: GREYNIR_PORT={0}".format(PORT_STR)
        )

    # Flask debug parameter
    DEBUG = False

    # Similarity server
    SIMSERVER_HOST = os.environ.get("SIMSERVER_HOST", "localhost")
    SIMSERVER_PORT_STR = os.environ.get("SIMSERVER_PORT", "5001")
    try:
        SIMSERVER_PORT = int(SIMSERVER_PORT_STR)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: SIMSERVER_PORT={0}".format(
                SIMSERVER_PORT_STR
            )
        )

    if SIMSERVER_PORT == PORT:
        raise ConfigError(
            "Can't run both main server and "
            "similarity server on port {0}".format(PORT)
        )

    NN_PARSING_ENABLED = os.environ.get("NN_PARSING_ENABLED", False)
    try:
        NN_PARSING_ENABLED = bool(int(NN_PARSING_ENABLED))
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: NN_PARSING_ENABLED = {0}".format(
                NN_PARSING_ENABLED
            )
        )
    NN_PARSING_HOST = os.environ.get("NN_PARSING_HOST", "localhost")
    NN_PARSING_PORT_STR = os.environ.get("NN_PARSING_PORT", "9000")
    try:
        NN_PARSING_PORT = int(NN_PARSING_PORT_STR)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: NN_PARSING_PORT = {0}".format(
                NN_PARSING_PORT_STR
            )
        )

    NN_TRANSLATION_ENABLED = os.environ.get("NN_TRANSLATION_ENABLED", False)
    try:
        NN_TRANSLATION_ENABLED = bool(int(NN_TRANSLATION_ENABLED))
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: NN_TRANSLATION_ENABLED = {0}".format(
                NN_TRANSLATION_ENABLED
            )
        )
    NN_TRANSLATION_HOST = os.environ.get("NN_TRANSLATION_HOST", "localhost")
    NN_TRANSLATION_PORT_STR = os.environ.get("NN_TRANSLATION_PORT", "9001")
    try:
        NN_TRANSLATION_PORT = int(NN_TRANSLATION_PORT_STR)
    except ValueError:
        raise ConfigError(
            "Invalid environment variable value: NN_TRANSLATION_PORT = {0}".format(
                NN_TRANSLATION_PORT_STR
            )
        )

    # Configuration settings from the Greynir.conf file
    @staticmethod
    def _handle_settings(s: str) -> None:
        """Handle config parameters in the settings section"""
        a = s.lower().split("=", maxsplit=1)
        par = a[0].strip().lower()
        sval = a[1].strip()
        val: Union[None, str, bool] = sval
        if sval.lower() == "none":
            val = None
        elif sval.lower() == "true":
            val = True
        elif sval.lower() == "false":
            val = False
        try:
            if par == "db_hostname":
                Settings.DB_HOSTNAME = str(val)
            elif par == "db_port":
                Settings.DB_PORT = int(val or 0)
            elif par == "bin_db_hostname":
                # This is no longer required and has been deprecated
                pass
            elif par == "bin_db_port":
                # This is no longer required and has been deprecated
                pass
            elif par == "host":
                Settings.HOST = str(val)
            elif par == "port":
                Settings.PORT = int(val or 0)
            elif par == "simserver_host":
                Settings.SIMSERVER_HOST = str(val)
            elif par == "simserver_port":
                Settings.SIMSERVER_PORT = int(val or 0)
            elif par == "debug":
                Settings.DEBUG = bool(val)
            else:
                raise ConfigError("Unknown configuration parameter '{0}'".format(par))
        except ValueError:
            raise ConfigError("Invalid parameter value: {0}={1}".format(par, val))

    @staticmethod
    def _handle_noindex_words(s: str) -> None:
        """Handle no index instructions in the settings section"""
        # Format: category = [cat] followed by word stem list
        a = s.lower().split("=", maxsplit=1)
        par = a[0].strip()
        if len(a) == 2:
            val = a[1].strip()
            if par == "category":
                NoIndexWords.set_cat(val)
            else:
                raise ConfigError("Unknown setting '{0}' in noindex_words".format(par))
            return
        assert len(a) == 1
        NoIndexWords.add(par)

    @staticmethod
    def read(fname: str) -> None:
        """Read configuration file"""

        with Settings._lock:

            if Settings.loaded:
                return

            CONFIG_HANDLERS = {
                "settings": Settings._handle_settings,
                "noindex_words": Settings._handle_noindex_words,
            }
            handler = None  # Current section handler

            rdr = None
            try:
                rdr = LineReader(fname)
                for s in rdr.lines():
                    # Ignore comments
                    ix = s.find("#")
                    if ix >= 0:
                        s = s[0:ix]
                    s = s.strip()
                    if not s:
                        # Blank line: ignore
                        continue
                    if s[0] == "[" and s[-1] == "]":
                        # New section
                        section = s[1:-1].strip().lower()
                        if section in CONFIG_HANDLERS:
                            handler = CONFIG_HANDLERS[section]
                            continue
                        raise ConfigError("Unknown section name '{0}'".format(section))
                    if handler is None:
                        raise ConfigError("No handler for config line '{0}'".format(s))
                    # Call the correct handler depending on the section
                    try:
                        handler(s)
                    except ConfigError as e:
                        # Add file name and line number information to the exception
                        # if it's not already there
                        e.set_pos(rdr.fname(), rdr.line())
                        raise e

            except ConfigError as e:
                # Add file name and line number information to the exception
                # if it's not already there
                if rdr:
                    e.set_pos(rdr.fname(), rdr.line())
                raise e

            Settings.loaded = True
