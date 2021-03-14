"""

    Greynir: Natural language processing for Icelandic

    High-level tokenizer and named entity recognizer

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


    This module exports recognize_entities(), a function which
    adds a named entity recognition layer on top of the reynir.bintokenizer
    functionality.

    Named entity recognition requires access to the SQL scraper database
    and is thus not appropriate for inclusion in reynir.bintokenizer,
    as GreynirPackage does not (and should not) require a database to be present.

"""

from typing import List, Iterator, Dict, Union, Tuple, Optional, Type

from collections import defaultdict
import logging

from reynir import Abbreviations, TOK, Tok
from reynir.bindb import BIN_Db

from db import SessionContext, OperationalError, Session
from db.models import Entity


def recognize_entities(
    token_stream: Iterator[Tok],
    enclosing_session: Optional[Session] = None,
    token_ctor: Type[TOK] = TOK,
) -> Iterator[Tok]:

    """ Parse a stream of tokens looking for (capitalized) entity names
        The algorithm implements N-token lookahead where N is the
        length of the longest entity name having a particular initial word.
        Adds a named entity recognition layer on top of the
        reynir.bintokenizer.tokenize() function.

    """

    # Token queue
    tq: List[Tok] = []
    # Phrases we're considering. Note that an entry of None
    # indicates that the accumulated phrase so far is a complete
    # and valid known entity name.
    state: Dict[Union[str, None], List[Tuple[List[str], Entity]]] = defaultdict(list)
    # Entitiy definition cache
    ecache: Dict[str, List[Entity]] = dict()
    # Last name to full name mapping ('Clinton' -> 'Hillary Clinton')
    lastnames: Dict[str, Tok] = dict()

    with BIN_Db.get_db() as db, SessionContext(
        session=enclosing_session, commit=True, read_only=True
    ) as session:

        def fetch_entities(w: str, fuzzy: bool=True) -> List[Entity]:
            """ Return a list of entities matching the word(s) given,
                exactly if fuzzy = False, otherwise also as a starting word(s) """
            try:
                q = session.query(Entity.name, Entity.verb, Entity.definition)
                if fuzzy:
                    q = q.filter(Entity.name.like(w + " %") | (Entity.name == w))
                else:
                    q = q.filter(Entity.name == w)
                return q.all()
            except OperationalError as e:
                logging.warning("SQL error in fetch_entities(): {0}".format(e))
                return []

        def query_entities(w: str) -> List[Entity]:
            """ Return a list of entities matching the initial word given """
            e = ecache.get(w)
            if e is None:
                ecache[w] = e = fetch_entities(w)
            return e

        def lookup_lastname(lastname: str) -> Optional[Tok]:
            """ Look up a last name in the lastnames registry,
                eventually without a possessive 's' at the end, if present """
            fullname = lastnames.get(lastname)
            if fullname is not None:
                # Found it
                return fullname
            # Try without a possessive 's', if present
            if lastname.endswith("s"):
                return lastnames.get(lastname[0:-1])
            # Nope, no match
            return None

        def flush_match():
            """ Flush a match that has been accumulated in the token queue """
            if len(tq) == 1 and lookup_lastname(tq[0].txt) is not None:
                # If single token, it may be the last name of a
                # previously seen entity or person
                return token_or_entity(tq[0])
            # Reconstruct original text behind phrase
            ename = " ".join([t.txt for t in tq])
            # We don't include the definitions in the token - they should be looked up
            # on the fly when processing or displaying the parsed article
            return token_ctor.Entity(ename)

        def token_or_entity(token: Tok) -> Tok:
            """ Return a token as-is or, if it is a last name of a person
                that has already been mentioned in the token stream by full name,
                refer to the full name """
            assert token.txt[0].isupper()
            tfull = lookup_lastname(token.txt)
            if tfull is None:
                # Not a last name of a previously seen full name
                return token
            if tfull.kind != TOK.PERSON:
                # Return an entity token with no definitions
                # (this will eventually need to be looked up by full name when
                # displaying or processing the article)
                return token_ctor.Entity(token.txt)
            # Return the full name meanings
            return token_ctor.Person(token.txt, tfull.val)

        try:

            while True:

                token = next(token_stream)

                if not token.txt:  # token.kind != TOK.WORD:
                    if state:
                        if None in state:
                            yield flush_match()
                        else:
                            yield from tq
                        tq = []
                        state = defaultdict(list)
                    yield token
                    continue

                # Look for matches in the current state and build a new state
                newstate = defaultdict(list)
                w = token.txt  # Original word

                def add_to_state(slist, entity):
                    """ Add the list of subsequent words to the new parser state """
                    wrd = slist[0] if slist else None
                    rest = slist[1:]
                    newstate[wrd].append((rest, entity))

                if w in state:
                    # This matches an expected token
                    tq.append(token)  # Add to lookahead token queue
                    # Add the matching tails to the new state
                    for sl, entity in state[w]:
                        add_to_state(sl, entity)
                    # Update the lastnames mapping
                    fullname = " ".join([t.txt for t in tq])
                    parts = fullname.split()
                    # If we now have 'Hillary Rodham Clinton',
                    # make sure we delete the previous 'Rodham' entry
                    for p in parts[1:-1]:
                        if p in lastnames:
                            del lastnames[p]
                    if parts[-1][0].isupper():
                        # 'Clinton' -> 'Hillary Rodham Clinton'
                        lastnames[parts[-1]] = token_ctor.Entity(fullname)
                else:
                    # Not a match for an expected token
                    if state:
                        if None in state:
                            # We have an accumulated match, but if the next token
                            # is an uppercase word without a BÍN meaning, we
                            # append it to the current entity regardless.
                            # This means that 'Charley Lucknow' is handled as a single
                            # new entity name even if 'Charley' already exists
                            # as an entity.
                            while w and w[0].isupper() and not token.val:
                                # Append to the accumulated token queue, which will
                                # be squashed to a single token in flush_match()
                                tq.append(token)
                                token = next(token_stream)
                                w = token.txt
                            # Flush the already accumulated match
                            yield flush_match()
                        else:
                            yield from tq
                        tq = []

                    # Add all possible new states for entity names
                    # that could be starting
                    weak = True
                    cnt = 1
                    upper = w and w[0].isupper()
                    parts = []

                    if upper and " " in w:
                        # For all uppercase phrases (words, entities, persons),
                        # maintain a map of last names to full names
                        parts = w.split()
                        lastname = parts[-1]
                        # Clinton -> Hillary [Rodham] Clinton
                        if lastname[0].isupper():
                            # Look for Icelandic patronyms/matronyms
                            _, m = db.lookup_word(lastname, False)
                            if m and any(mm.fl in {"föð", "móð"} for mm in m):
                                # We don't store Icelandic patronyms/matronyms
                                # as surnames
                                pass
                            else:
                                lastnames[lastname] = token

                    if token.kind == TOK.WORD and upper and w not in Abbreviations.DICT:
                        if " " in w:
                            # w may be a person name with more than one embedded word
                            # parts is assigned in the if statement above
                            cnt = len(parts)
                        elif not token.val or ("-" in token.val[0].stofn):
                            # No BÍN meaning for this token, or the meanings
                            # were constructed by concatenation (indicated by a hyphen
                            # in the stem)
                            weak = False  # Accept single-word entity references
                        # elist is a list of Entity instances
                        elist = query_entities(w)
                    else:
                        elist = []

                    if elist:
                        # This word might be a candidate to start an entity reference
                        candidate = False
                        for e in elist:
                            # List of subsequent words in entity name
                            sl = e.name.split()[cnt:]
                            if sl:
                                # Here's a candidate for a longer entity reference
                                # than we already have
                                candidate = True
                            if sl or not weak:
                                add_to_state(sl, e)
                        if weak and not candidate:
                            # Found no potential entity reference longer than this token
                            # already is - and we have a BÍN meaning for it:
                            # Abandon the effort
                            assert not newstate
                            assert not tq
                            yield token_or_entity(token)
                        else:
                            # Go for it: Initialize the token queue
                            tq = [token]
                    else:
                        # Not a start of an entity reference: simply yield the token
                        assert not tq
                        if upper:
                            # Might be a last name referring to a full name
                            yield token_or_entity(token)
                        else:
                            yield token

                # Transition to the new state
                state = newstate

        except StopIteration:
            # Token stream is exhausted
            pass

        # Yield an accumulated match if present
        if state:
            if None in state:
                yield flush_match()
            else:
                yield from tq
            tq = []

    # print("\nEntity cache:\n{0}".format("\n".join("'{0}': {1}".format(k, v) for k, v in ecache.items())))
    # print("\nLast names:\n{0}".format("\n".join("{0}: {1}".format(k, v) for k, v in lastnames.items())))

    assert not tq
