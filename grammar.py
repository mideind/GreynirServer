"""
    Reynir: Natural language processing for Icelandic

    Grammar module

    Author: Vilhjalmur Thorsteinsson

    This software is at a very early development stage.
    While that is the case, it is:
    Copyright (c) 2015 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    A grammar is specified as a set of rules. Each rule has a single
    left-hand-side nonterminal, associated with 1..n right-hand-side
    productions. Each right-hand-side production is a sequence of
    nonterminals and terminals. A terminal can match a token of
    input.

    In Reynir grammars, nonterminals always start with an uppercase letter.
    Terminals may be identifiers starting with lowercase letters, or
    literals enclosed within single or double quotes. Epsilon (empty)
    productions are allowed and denoted by 0.

"""

import codecs

from pprint import pprint as pp


class GrammarError(Exception):

    """ Exception class for errors in a grammar """

    def __init__(self, text, fname = None, line = 0):

        """ A GrammarError contains an error text and optionally the name
            of a grammar file and a line number where the error occurred """

        self.fname = fname
        self.line = line
        prefix = ""
        if line:
            prefix = "Line " + str(line) + ": "
        if fname:
            prefix = fname + " - " + prefix
        Exception.__init__(self, prefix + text)


class Nonterminal:

    """ A nonterminal, either at the left hand side of
        a rule or within a production """

    def __init__(self, name, fname = None, line = 0):
        self.name = name
        # Place of initial definition in a grammar file
        self._fname = fname
        self._line = line
        # Has this nonterminal been referenced in a production?
        self._ref = False

    def add_ref(self):
        """ Mark this as being referenced """
        self._ref = True

    def has_ref(self):
        """ Return True if the nonterminal has been referenced in a production """
        return self._ref

    def fname(self):
        """ Return the name of the grammar file where this nonterminal was defined """
        return self._fname

    def line(self):
        """ Return the number of the line within the grammar file where this nt was defined """
        return self._line

    def __eq__(self, other):
        return isinstance(other, Nonterminal) and self.name == other.name

    def __ne__(self, other):
        return not isinstance(other, Nonterminal) or self.name != other.name

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return '<{0}>'.format(self.name)

    def __str__(self):
        return '<{0}>'.format(self.name)


class Terminal:

    """ A terminal within a right-hand-side production """

    def __init__(self, name):
        self.name = name
        # Do a bit of pre-calculation to speed up various
        # checks against this terminal
        self.parts = name.split("_")
        # The variant set for this terminal, i.e.
        # tname_var1_var2_var3 -> { 'var1', 'var2', 'var3' }
        self.vset = set(self.parts[1:])

    def __hash__(self):
        return hash(self.name)

    def __repr__(self):
        return '{0}'.format(self.name)

    def __str__(self):
        return '{0}'.format(self.name)

    def has_variant(self, v):
        """ Returns True if the terminal name has the given variant """
        return v in self.vset

    def num_variants(self):
        """ Return the number of variants in the terminal name """
        return len(self.parts) - 1

    def variants(self):
        """ Returns the variants contained in this terminal name as a list """
        return self.parts[1:]

    def variant(self, index):
        """ Return the variant with the given index """
        assert index >= 0
        return self.parts[1 + index]

    def startswith(self, part):
        """ Returns True if the terminal name starts with the given string """
        return self.parts[0] == part

    def matches(self, t_kind, t_val):
        # print("Terminal.matches: self.name is {0}, t_kind is {1}".format(self.name, t_kind))
        return self.name == t_kind

    def matches_first(self, t_kind, t_val):
        return self.parts[0] == t_kind


class LiteralTerminal(Terminal):

    """ A literal (constant string) terminal within a right-hand-side production """

    def __init__(self, lit):
        Terminal.__init__(self, lit)

    def matches(self, t_kind, t_val):
        """ A literal terminal matches a token if the token text is identical to the literal """
        return self.name == t_val

    def matches_first(self, t_kind, t_val):
        """ A literal terminal matches a token if the token text is identical to the literal """
        return self.parts[0] == t_val

    def __repr__(self):
        return '\'{0}\''.format(self.name)

    def __str__(self):
        return '\'{0}\''.format(self.name)


class Token:

    """ A token from the input stream tokenizer """

    def __init__(self, kind, val):
        """ A basic token has a kind and a value, both strings """
        self.kind = kind
        self.val = val

    def __repr__(self):
        """ Return a simple string representation of this token """
        if self.kind == self.val:
            return '{0}'.format(self.kind)
        return '{0}:{1}'.format(self.kind, self.val)

    def text(self):
        """ Return the token text, as it was in the source """
        return self.val

    def matches(self, terminal):
        """ Does this token match the given terminal? """
        # By default, ask the terminal
        return terminal.matches(self.kind, self.val)


class Production:

    """ A right-hand side of a grammar rule """

    _INDEX = 0 # Running sequence number of all productions

    def __init__(self, fname = None, line = 0, rhs = None):

        """ Initialize a production from a list of
            right-hand-side nonterminals and terminals """

        self._rhs = [] if rhs is None else rhs
        # If parsing a grammar file, note the position of the production
        # in the file
        self._fname = fname
        self._line = line
        # Give all productions a unique sequence number for hashing purposes
        self._index = Production._INDEX
        Production._INDEX += 1

    def __hash__(self):
        """ Use the index of this production as a basis for the hash """
        return self._index.__hash__()

    def __eq__(self, other):
        return isinstance(other, Production) and self._index == other._index

    def __ne__(self, other):
        return not isinstance(other, Production) or self._index != other._index

    def append(self, t):
        """ Append a terminal or nonterminal to this production """
        self._rhs.append(t)

    def expand(self, l):
        """ Add a list of terminals and/or nonterminals to this production """
        self._rhs.expand(l)

    def length(self):
        """ Return the length of this production """
        return len(self._rhs)

    def is_empty(self):
        """ Return True if this is an empty (epsilon) production """
        return len(self._rhs) == 0

    def fname(self):
        return self._fname

    def line(self):
        return self._line

    def __getitem__(self, index):
        """ Return the terminal or nonterminal at the given index position """
        return self._rhs[index]

    def __len__(self):
        """ Return the length of this production """
        return len(self._rhs)

    def __repr__(self):
        """ Return a representation of this production """
        return "<Production: " + repr(self._rhs) + ">"

    def __str__(self):
        """ Return a representation of this production """
        return " ".join([str(t) for t in self._rhs]) if self._rhs else "0"


class Grammar:

    """
        A grammar maps nonterminals to a list of right hand sides.
        Each right hand side is a list of terminals and nonterminals.

        The text representation of a grammar is as follows:

        A -> A B terminal C
            | A '/' D
            | 0
        B -> terminal "+" C

        Nonterminals start with uppercase letters.

        Terminals start with lowercase letters or are enclosed
        in single or double quotes.

        0 means an empty (epsilon) production.

    """

    def __init__(self):
        self._nonterminals = { }
        self._terminals = { }
        self._nt_dict = { }
        self._root = None

    def nt_dict(self):
        """ Return the raw grammar dictionary, Nonterminal -> [ Productions ] """
        return self._nt_dict

    def root(self):
        """ Return the root nonterminal for this grammar """
        return self._root

    def num_nonterminals(self):
        """ Return the number of nonterminals in the grammar """
        return len(self._nonterminals)

    def num_terminals(self):
        """ Return the number of terminals in the grammar """
        return len(self._terminals)

    def num_productions(self):
        """ Return the total number of productions in the grammar,
            were each right hand side option is counted as one """
        return sum(len(nt_p) for nt_p in self._nt_dict.values())

    def __str__(self):

        def to_str(plist):
            return " | ".join([str(p) for p in plist])

        return "".join([str(nt) + " → " + to_str(plist) + "\n" for nt, plist in self._nt_dict.items()])

    def read(self, fname):
        """ Read grammar from a text file """

        # Shortcuts
        terminals = self._terminals
        nonterminals = self._nonterminals
        grammar = self._nt_dict
        line = 0

        current_NT = None
        current_variants = []
        variants = { }
        current_line = ""

        def parse_line(s):

            s = s.strip()
            if not s:
                # Blank line: ignore
                return

            def _add_rhs(nt_id, rhs):
                """ Add a right-hand-side production to a nonterminal rule """
                nt = nonterminals[nt_id]
                if nt not in grammar:
                    grammar[nt] = [ ] if rhs is None else [ rhs ]
                    return
                if rhs is None:
                    return
                if rhs.is_empty():
                    # Adding epsilon production: avoid multiple ones
                    if any(p.is_empty() for p in grammar[nt]):
                        return
                grammar[nt].append(rhs)

            def _parse_rhs(nt_id, vts, s):
                """ Parse a right-hand side sequence """
                s = s.strip()
                if not s:
                    raise GrammarError("Invalid syntax for production", fname, line)

                tokens = s.split()

                # rhs is a list of tuples, one for each token, as follows:
                # (id, repeat, variants)
                rhs = []

                for r in tokens:

                    if r == "0":
                        # Empty (epsilon) production
                        if len(tokens) != 1:
                            raise GrammarError("Empty (epsilon) rule must be of the form NT -> 0", fname, line)
                        rhs.append((None, None, None))
                        break

                    # Check for repeat/conditionality
                    repeat = None
                    if r[-1] in '*+?':
                        # Optional repeat/conditionality specifier
                        # Asterisk: Can be repeated 0 or more times
                        # Plus: Can be repeated 1 or more times
                        # Question mark: optionally present once
                        repeat = r[-1]
                        r = r[0:-1]

                    # Check for variant specs
                    v = r.split('/')
                    r = v[0]
                    v = v[1:]
                    if not v:
                        v = None
                    else:
                        for vspec in v:
                            if vspec not in vts:
                                raise GrammarError("Variant '{0}' not specified for nonterminal '{1}'".format(vspec, nt_id), fname, line)

                    if r[0] in "\"'":
                        # Literal terminal symbol
                        if len(r) < 3 or r[-1] != r[0]:
                            raise GrammarError("Invalid literal terminal '{0}'".format(r), fname, line)
                    else:
                        # Identifier of nonterminal or terminal
                        if not r.isidentifier():
                            raise GrammarError("Invalid identifier '{0}'".format(r), fname, line)
                    rhs.append((r, repeat, v))

                assert len(rhs) == len(tokens)

                # Generate productions for all variants

                def variant_values(vts):
                    """ Returns a list of names with all applicable variant options appended """
                    if not vts:
                        yield [ "" ]
                        return
                    if len(vts) == 1:
                        for vopt in variants[vts[0]]:
                            yield [ vopt ]
                        return
                    for v in variant_values(vts[1:]):
                        for vopt in variants[vts[0]]:
                            yield [ vopt ] + v

                # print("Variants are: {0}".format(vts))

                for vval in variant_values(vts):
                    # Generate a production for every variant combination
                    # print("Processing combination {0}".format(vval))
                    result = Production(fname, line)
                    for r, repeat, v in rhs:
                        # Calculate the identifier suffix, if any
                        suffix = "_".join(vval[vts.index(vx)] for vx in v) if v else ""
                        if suffix:
                            suffix = "_" + suffix
                        if r is None:
                            # Epsilon
                            n = None
                        elif r[0] in "'\"":
                            # Literal token
                            sym = r + suffix
                            lit = r[1:-1]
                            if sym not in terminals:
                                terminals[sym] = LiteralTerminal(lit)
                            n = terminals[sym]
                        else:
                            # Identifier for terminal or nonterminal
                            if r[0].isupper():
                                # Reference to nonterminal
                                if r + suffix not in nonterminals:
                                    nonterminals[r + suffix] = Nonterminal(r + suffix, fname, line)
                                nonterminals[r + suffix].add_ref() # Note that the nonterminal has been referenced
                                n = nonterminals[r + suffix]
                            else:
                                # Identifier of terminal
                                if r + suffix not in terminals:
                                    terminals[r + suffix] = Terminal(r + suffix)
                                n = terminals[r + suffix]

                        # If the production item can be repeated,
                        # create a new production and substitute.
                        # A -> B C* D becomes:
                        # A -> B C_new_* D
                        # C_new_* -> C_new_* C | 0
                        # A -> B C+ D becomes:
                        # A -> B C_new_+ D
                        # C_new_+ -> C_new_+ C | C
                        # A -> B C? D becomes:
                        # A -> B C_new_? D
                        # C_new_? -> C | 0

                        if repeat is not None:
                            new_nt_id = r + suffix + repeat
                            # Make the new nonterminal and production if not already there
                            if new_nt_id not in nonterminals:
                                new_nt = nonterminals[new_nt_id] = Nonterminal(new_nt_id, fname, line)
                                new_nt.add_ref()
                                # First production: C_new_x C
                                new_p = Production(fname, line)
                                if repeat != '?':
                                    new_p.append(new_nt) # C_new_x
                                new_p.append(n) # C
                                _add_rhs(new_nt_id, new_p)
                                # Second production: epsilon(*, ?) or C(+)
                                new_p = Production(fname, line)
                                if repeat == '+':
                                    new_p.append(n)
                                _add_rhs(new_nt_id, new_p)
                            # Substitute the C_new_x in the original production
                            n = nonterminals[new_nt_id]

                        if n is not None:
                            result.append(n)

                    assert len(result) == len(rhs) or (len(rhs) == 1 and rhs[0] == (None, None, None))

                    nt_id_full = "_".join([ nt_id ] + vval) if vts else nt_id

                    if len(result) == 1 and result[0] == nonterminals[nt_id_full]:
                        # Nonterminal derives itself
                        raise GrammarError("Nonterminal {0} deriving itself".format(nt_id), fname, line)
                    _add_rhs(nt_id_full, result)

            def variant_names(nt, vts):
                """ Returns a list of names with all applicable variant options appended """
                result = [ nt ]
                for v in vts:
                    newresult = []
                    for vopt in variants[v]:
                        for r in result:
                            newresult.append(r + "_" + vopt)
                    result = newresult
                return result

            if s.startswith('/'):
                # Definition of variant
                # A variant is specified as /varname = opt1 opt2 opt3...
                v = s.split('=', maxsplit = 1)
                if len(v) != 2:
                    raise GrammarError("Invalid variant syntax", fname, line)
                vname = v[0].strip()[1:]
                if not vname.isidentifier():
                    raise GrammarError("Invalid variant name '{0}'".format(vname), fname, line)
                v = v[1].split()
                for vopt in v:
                    if not vopt.isidentifier():
                        raise GrammarError("Invalid option '{0}' in variant '{1}'".format(vopt, vname), fname, line)
                variants[vname] = v
            else:
                # New nonterminal
                if "→" in s:
                    # Fancy schmancy arrow sign: use it
                    rule = s.split("→", maxsplit=1)
                else:
                    rule = s.split("->", maxsplit=1)
                if len(rule) != 2:
                    raise GrammarError("Invalid syntax", fname, line)
                # Split nonterminal spec into name and variant(s),
                # i.e. NtName/var1/var2...
                ntv = rule[0].strip().split('/')
                current_NT = nt = ntv[0]
                current_variants = ntv[1:]
                if not nt.isidentifier():
                    raise GrammarError("Invalid nonterminal name '{0}'".format(nt), fname, line)
                for vname in current_variants:
                    if vname not in variants:
                        raise GrammarError("Unknown variant '{0}' for nonterminal '{1}'".format(vname, nt), fname, line)
                var_names = variant_names(nt, current_variants)

                # Add all previously unknown nonterminal variants
                for nt_var in var_names:
                    if nt_var in nonterminals:
                        cnt = nonterminals[nt_var]
                    else:
                        cnt = Nonterminal(nt_var, fname, line)
                        nonterminals[nt_var] = cnt
                        if self._root is None:
                            # Remember first nonterminal as the root
                            self._root = cnt
                            self._root.add_ref() # Implicitly referenced
                    if cnt not in grammar:
                        grammar[cnt] = [ ]

                for prod in rule[1].split("|"):
                    # Add the productions on the right hand side, delimited by vertical bars
                    _parse_rhs(current_NT, current_variants, prod)

        # Main parse loop

        try:
            with codecs.open(fname, "r", "utf-8") as inp:
                # Read grammar file line-by-line

                for s in inp:

                    line += 1
                    # Ignore comments
                    ix = s.find('#')
                    if ix >= 0:
                        s = s[0:ix]

                    if not s:
                        continue

                    # If line starts with a blank, assume it's a continuation
                    if s[0].isspace():
                        current_line += s
                        continue

                    # New item starting: parse the previous one and start a new
                    parse_line(current_line)
                    current_line = s

                # Parse the final chunk
                parse_line(current_line)

        except (IOError, OSError):
            raise GrammarError("Unable to open or read grammar file", fname, 0)

        # Check all nonterminals to verify that they have productions and are referenced
        for nt in nonterminals.values():
            if not nt.has_ref():
                raise GrammarError("Nonterminal {0} is never referenced in a production".format(nt), nt.fname(), nt.line())
            if nt not in grammar:
                raise GrammarError("Nonterminal {0} is referenced but not defined".format(nt), nt.fname(), nt.line())
        for nt, plist in grammar.items():
            if len(plist) == 0:
                raise GrammarError("Nonterminal {0} has no productions".format(nt), nt.fname(), nt.line())
            else:
                for p in plist:
                    if len(p) == 1 and plist[0] == nt:
                        raise GrammarError("Nonterminal {0} produces itself".format(nt), p.fname(), p.line())

        # Check that all nonterminals derive terminal strings
        agenda = [ nt for nt in nonterminals.values() ]
        der_t = set()
        while agenda:
            reduced = False
            for nt in agenda:
                for p in grammar[nt]:
                    if all([True if isinstance(s, Terminal) else s in der_t for s in p]):
                        der_t.add(nt)
                        break
                if nt in der_t:
                    reduced = True
            if not reduced:
                break
            agenda = [ nt for nt in nonterminals.values() if nt not in der_t ]
        if agenda:
            raise GrammarError("Nonterminals {0} do not derive terminal strings"
                .format(", ".join([str(nt) for nt in agenda])), fname, 0)

        # Check that all nonterminals are reachable from the root
        unreachable = { nt for nt in nonterminals.values() }

        def _remove(nt):
            """ Recursively remove all nonterminals that are reachable from nt """
            unreachable.remove(nt)
            for p in grammar[nt]:
                for s in p:
                    if isinstance(s, Nonterminal) and s in unreachable:
                        _remove(s)

        _remove(self._root)

        if unreachable:
            raise GrammarError("Nonterminals {0} are unreachable from the root"
                .format(", ".join([str(nt) for nt in unreachable])), fname, 0)

