"""

    Greynir: Natural language processing for Icelandic

    Scraper database initialization module

    Copyright (C) 2021 Miðeind ehf.

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
from time import sleep

from . import SessionContext, IntegrityError
from .models import Root


ROOTS = [
    # Root URL, top-level domain, description, authority, scr_module, scr_class, scrape
    (
        "https://kjarninn.is",
        "kjarninn.is",
        "Kjarninn",
        1.0,
        "scrapers.default",
        "KjarninnScraper",
        True,
    ),
    (
        "https://www.ruv.is",
        "ruv.is",
        "RÚV",
        1.0,
        "scrapers.default",
        "RuvScraper",
        True,
    ),
    (
        "https://www.visir.is",
        "visir.is",
        "Vísir",
        0.8,
        "scrapers.default",
        "VisirScraper",
        True,
    ),
    (
        "https://www.mbl.is/frettir/",
        "mbl.is",
        "Morgunblaðið",
        0.6,
        "scrapers.default",
        "MblScraper",
        True,
    ),
    (
        "https://kvennabladid.is",
        "kvennabladid.is",
        "Kvennablaðið",
        0.4,
        "scrapers.default",
        "KvennabladidScraper",
        True,
    ),
    (
        "http://stjornlagarad.is",
        "stjornlagarad.is",
        "Stjórnlagaráð",
        1.0,
        "scrapers.default",
        "StjornlagaradScraper",
        True,
    ),
    (
        "https://www.forsaetisraduneyti.is",
        "forsaetisraduneyti.is",
        "Forsætisráðuneyti",
        1.0,
        "scrapers.default",
        "StjornarradScraper",
        True,
    ),
    (
        "https://www.innanrikisraduneyti.is",
        "innanrikisraduneyti.is",
        "Innanríkisráðuneyti",
        1.0,
        "scrapers.default",
        "StjornarradScraper",
        True,
    ),
    (
        "https://www.fjarmalaraduneyti.is",
        "fjarmalaraduneyti.is",
        "Fjármálaráðuneyti",
        1.0,
        "scrapers.default",
        "StjornarradScraper",
        True,
    ),
    # (
    #     "http://reykjanes.local",
    #     "reykjanes.local",
    #     "Reykjanesbær",
    #     1.0,
    #     "scrapers.reykjanes",
    #     "ReykjanesScraper",
    #     False,
    # ),
    (
        "https://althingi.is",
        "althingi.is",
        "Alþingi",
        1.0,
        "scrapers.default",
        "AlthingiScraper",
        False,
    ),
    (
        "https://stundin.is",
        "stundin.is",
        "Stundin",
        1.0,
        "scrapers.default",
        "StundinScraper",
        True,
    ),
    # (
    #     "https://hringbraut.frettabladid.is",
    #     "hringbraut.is",
    #     "Hringbraut",
    #     1.0,
    #     "scrapers.default",
    #     "HringbrautScraper",
    #     True,
    # ),
    (
        "https://www.frettabladid.is/",
        "frettabladid.is",
        "Fréttablaðið",
        1.0,
        "scrapers.default",
        "FrettabladidScraper",
        True,
    ),
    (
        "https://www.utanrikisraduneyti.is",
        "utanrikisraduneyti.is",
        "Utanríkisráðuneyti",
        1.0,
        "scrapers.default",
        "StjornarradScraper",
        True,
    ),
    (
        "https://hagstofa.is",
        "hagstofa.is",
        "Hagstofa Íslands",
        1.0,
        "scrapers.default",
        "HagstofanScraper",
        True,
    ),
    ("https://www.dv.is/", "dv.is", "DV", 0.4, "scrapers.default", "DVScraper", True,),
    ("http://www.bb.is/", "bb.is", "BB", 0.4, "scrapers.default", "BBScraper", True,),
    (
        "https://lemurinn.is/",
        "lemurinn.is",
        "Lemúrinn",
        0.4,
        "scrapers.default",
        "LemurinnScraper",
        True,
    ),
    (
        "https://man.is/",
        "man.is",
        "Mannlíf",
        0.4,
        "scrapers.default",
        "MannlifScraper",
        True,
    ),
    # (
    #     "https://visindavefur.is/",
    #     "visindavefur.is",
    #     "Vísindavefurinn",
    #     1.0,
    #     "scrapers.default",
    #     "VisindavefurScraper",
    #     True,
    # ),
    (
        "https://sedlabanki.is/",
        "sedlabanki.is",
        "Seðlabankinn",
        1.0,
        "scrapers.default",
        "SedlabankinnScraper",
        True,
    ),
]


def init_roots(wait=False):
    """ Create tables and initialize the scraping roots, if not already present.
        If wait = True, repeated attempts are made to connect to the database
        before returning an error code. This is useful for instance in a Docker
        environment where the container may need to wait for a linked database
        container to start serving. """

    # Do no more than 36 retries (~3 minutes) before giving up and returning an error code
    retries = 36

    while True:

        try:

            db = SessionContext.db
            # pylint: disable=no-member
            db.create_tables()

            with SessionContext() as session:
                for (
                    url,
                    domain,
                    description,
                    authority,
                    scr_module,
                    scr_class,
                    scrape,
                ) in ROOTS:
                    r = Root(
                        url=url,
                        domain=domain,
                        description=description,
                        authority=authority,
                        scr_module=scr_module,
                        scr_class=scr_class,
                        scrape=scrape,
                        visible=scrape and not domain.endswith(".local"),
                    )
                    session.add(r)
                    try:
                        # Commit the insert
                        session.commit()
                    except IntegrityError:
                        # The root already exist: roll back and continue
                        session.rollback()

                rlist = session.query(Root).all()
                print("Roots initialized as follows:")
                for r in rlist:
                    print("{0:24} {1:36} {2:24}".format(r.domain, r.url, r.scr_class))

            # Done without error, break out of enclosing while True loop
            break

        except Exception as e:
            if wait:
                # If we want to wait until the database responds, sleep and loop
                # (this is most common in a Docker situation where we need to wait
                # for the postgres container to come online before continuing)
                print("PostgreSQL is not yet accepting connections.", file=sys.stderr)
                if not retries:
                    return 2  # No more retries: Return an error code
                print(
                    "Retrying connection in 5 seconds ({0} retries left)...".format(
                        retries
                    ),
                    file=sys.stderr,
                )
                sys.stderr.flush()
                sleep(5)
                retries -= 1
                SessionContext.cleanup()
                # Loop to retry
            else:
                print("Exception in init_roots(): {0}".format(e), file=sys.stderr)
                sys.stderr.flush()
                # Re-raise the exception
                raise

    # Finished without error
    return 0
