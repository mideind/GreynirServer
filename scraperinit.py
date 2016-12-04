#!/usr/bin/env python

"""

    Reynir: Natural language processing for Icelandic

    Scraper database initialization module

    Copyright (C) 2016 Vilhjálmur Þorsteinsson

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


    This module creates the scraper database tables, if they don't already
    exist. It also populates the roots table if needed.

"""

import sys

from settings import Settings, ConfigError
from scraperdb import SessionContext, Root, IntegrityError


def init_roots():
    """ Create tables and initialize the scraping roots, if not already present """

    try:
        Settings.read("config/Reynir.conf")
        # Don't run the scraper in debug mode
        Settings.DEBUG = False
    except ConfigError as e:
        print("Configuration error: {0}".format(e), file = sys.stderr)
        sys.exit(2)

    db = SessionContext.db

    try:

        db.create_tables()

        ROOTS = [
            # Root URL, top-level domain, description, authority
            ("http://kjarninn.is", "kjarninn.is", "Kjarninn", 1.0, "scrapers.default", "KjarninnScraper", True),
            ("http://www.ruv.is", "ruv.is", "RÚV", 1.0, "scrapers.default", "RuvScraper", True),
            ("http://www.visir.is", "visir.is", "Vísir", 0.8, "scrapers.default", "VisirScraper", True),
            ("http://www.mbl.is/frettir/", "mbl.is", "Morgunblaðið", 0.6, "scrapers.default", "MblScraper", True),
            ("http://eyjan.pressan.is", "eyjan.pressan.is", "Eyjan", 0.4, "scrapers.default", "EyjanScraper", True),
            ("http://kvennabladid.is", "kvennabladid.is", "Kvennablaðið", 0.4, "scrapers.default", "KvennabladidScraper", True),
            ("http://stjornlagarad.is", "stjornlagarad.is", "Stjórnlagaráð", 1.0, "scrapers.default", "StjornlagaradScraper", True),
            ("https://www.forsaetisraduneyti.is", "forsaetisraduneyti.is", "Forsætisráðuneyti", 1.0, "scrapers.default", "StjornarradScraper", True),
            ("https://www.innanrikisraduneyti.is", "innanrikisraduneyti.is", "Innanríkisráðuneyti", 1.0, "scrapers.default", "StjornarradScraper", True),
            ("https://www.fjarmalaraduneyti.is", "fjarmalaraduneyti.is", "Fjármálaráðuneyti", 1.0, "scrapers.default", "StjornarradScraper", True),
            ("http://reykjanes.local", "reykjanes.local", "Reykjanesbær", 1.0, "scrapers.reykjanes", "ReykjanesScraper", False),
            ("http://althingi.is", "althingi.is", "Alþingi", 1.0, "scrapers.default", "AlthingiScraper", False)
        ]

        with SessionContext() as session:
            for url, domain, description, authority, scr_module, scr_class, scrape in ROOTS:
                r = Root(url = url, domain = domain, description = description, authority = authority,
                    scr_module = scr_module, scr_class = scr_class, scrape = scrape,
                    visible = scrape and not domain.endswith(".local"))
                session.add(r)
                try:
                    # Commit the insert
                    session.commit()
                except IntegrityError as e:
                    # The root already exist: roll back and continue
                    session.rollback()

            rlist = session.query(Root).all()
            print("Roots initialized as follows:")
            for r in rlist:
                print("{0}".format(r))

    except Exception as e:
        print("{0}".format(e))


if __name__ == "__main__":

    init_roots()
