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

import os
import struct
from datetime import datetime


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

    _INDEX = -1 # Running sequence number (negative) of all nonterminals

    def __init__(self, name, fname = None, line = 0):
        self._name = name
        # Place of initial definition in a grammar file
        self._fname = fname
        self._line = line
        # Has this nonterminal been referenced in a production?
        self._ref = False
        # Give all nonterminals a unique, negative sequence number for hashing purposes
        self._index = Nonterminal._INDEX
        Nonterminal._INDEX -= 1

    def __hash__(self):
        """ Use the id of this nonterminal as a basis for the hash """
        # The index may change after the entire grammar has been
        # read and processed; therefore it is not suitable for hashing
        return id(self).__hash__()

    def __eq__(self, other):
        return id(self) == id(other)

    def __ne__(self, other):
        return id(self) != id(other)

    @property
    def index(self):
        """ Return the (negative) sequence number of this nonterminal """
        return self._index

    def set_index(self, ix):
        """ Set a new sequence number for this nonterminal """
        assert ix < 0
        self._index = ix

    def add_ref(self):
        """ Mark this as being referenced """
        self._ref = True

    @property
    def has_ref(self):
        """ Return True if the nonterminal has been referenced in a production """
        return self._ref

    @property
    def name(self):
        return self._name

    @property
    def fname(self):
        """ Return the name of the grammar file where this nonterminal was defined """
        return self._fname

    @property
    def line(self):
        """ Return the number of the line within the grammar file where this nt was defined """
        return self._line

    def __repr__(self):
        return '{0}'.format(self._name)

    def __str__(self):
        return '{0}'.format(self._name)


class Terminal:

    """ A terminal within a right-hand-side production """

    _INDEX = 1 # Running sequence number (positive) of all terminals

    def __init__(self, name):
        self._name = name
        self._index = Terminal._INDEX
        # The hash is used quite often so it is worth caching
        self._hash = id(self).__hash__()
        Terminal._INDEX += 1

    def __hash__(self):
        return self._hash

    def __repr__(self):
        return '{0}'.format(self._name)

    def __str__(self):
        return '{0}'.format(self._name)

    @property
    def name(self):
        return self._name
    
    @property
    def index(self):
        """ Return the (positive) sequence number of this terminal """
        return self._index

    def set_index(self, ix):
        """ Set a new sequence number for this nonterminal """
        assert ix > 0
        self._index = ix

    def matches(self, t_kind, t_val, t_lit):
        # print("Terminal.matches: self.name is {0}, t_kind is {1}".format(self.name, t_kind))
        return self._name == t_kind


class LiteralTerminal(Terminal):

    """ A literal (constant string) terminal within a right-hand-side production.
        A literal within single quotes 'x' is matched canonically, i.e. with
        the corresponding word stem, if available.
        A literal within double quotes "x" is matched absolutely, i.e. with
        the exact source text (except for a conversion to lowercase). """

    def __init__(self, lit):
        # Replace any underscores within the literal with spaces, allowing literals
        # to match tokens with spaces in them
        q = lit[0]
        assert q in "\'\""
        ix = lit[1:].index(q) + 1 # Find closing quote
        # Replace underscores within the literal with spaces
        lit = lit[0:ix + 1].replace("_", " ") + lit[ix + 1:]
        super().__init__(lit)
        # If a double quote was used, this is a 'strong' literal
        # that matches an exact terminal string as it appeared in the source
        # - no stemming or other canonization should be applied,
        # although the string will be converted to lowercase
        self._strong = (q == '\"')

    def matches(self, t_kind, t_val, t_lit):
        """ A literal terminal matches a token if the token text is
            canonically or absolutely identical to the literal """
        if self._strong:
            # Absolute literal match
            return self._name == t_lit
        # Canonical match of stems or prototypes
        return self._name == t_val


class Token:

    """ A single input token as seen by the parser """

    def __init__(self, kind, val, lit = None):
        """ A basic token has a kind, a canonical value and an optional literal value,
            all strings """
        self._kind = kind
        self._val = val
        self._lit = lit or val

    def __repr__(self):
        """ Return a simple string representation of this token """
        if self._kind == self._val:
            return '{0}'.format(self._kind)
        return '{0}:{1}'.format(self._kind, self._val)

    @property
    def kind(self):
        """ Return the token kind """
        return self._kind

    @property
    def text(self):
        """ Return the 'canonical' token text, which may be a stem or
            prototype of the literal, original token text as it appeared
            in the source """
        return self._val

    @property
    def literal(self):
        """ Return the literal, original token text as it appeared in the source """
        return self._lit

    def matches(self, terminal):
        """ Does this token match the given terminal? """
        # By default, ask the terminal
        return terminal.matches(self._kind, self._val, self._lit)


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
        # Cache the length of the production as it is used A LOT
        self._len = len(self._rhs)
        # Give all productions a unique sequence number for hashing purposes
        self._index = Production._INDEX
        Production._INDEX += 1
        # Cached tuple representation of this production
        self._tuple = None

    def __hash__(self):
        """ Use the index of this production as a basis for the hash """
        return self._index.__hash__()

    def __eq__(self, other):
        #return isinstance(other, Production) and self._index == other._index
        return id(self) == id(other)

    def __ne__(self, other):
        #return not isinstance(other, Production) or self._index != other._index
        return id(self) != id(other)

    def append(self, t):
        """ Append a terminal or nonterminal to this production """
        self._rhs.append(t)
        self._len += 1
        # Destroy the cached tuple, if any
        self._tuple = None

    def expand(self, l):
        """ Add a list of terminals and/or nonterminals to this production """
        self._rhs.expand(l)
        self._len += len(l)
        # Destroy the cached tuple, if any
        self._tuple = None

    @property
    def length(self):
        """ Return the length of this production """
        return self._len

    @property
    def is_empty(self):
        """ Return True if this is an empty (epsilon) production """
        return self._len == 0

    @property
    def fname(self):
        return self._fname

    @property
    def line(self):
        return self._line

    @property
    def prod(self):
        """ Return this production in tuple form """
        if self._tuple is None:
            # Nonterminals have negative indices and terminals have positive ones
            self._tuple = tuple(t.index for t in self._rhs) if self._rhs else tuple()
        return self._tuple

    def nonterminal_at(self, dot):
        """ Return True if prod[dot] is a nonterminal or completed """
        return dot >= self._len or isinstance(self._rhs[dot], Nonterminal)

    def __getitem__(self, index):
        """ Return the Terminal or Nonterminal at the given index position """
        return self._rhs[index]

    def __setitem__(self, index, val):
        """ Set the Terminal or Nonterminal at the given index position """
        self._rhs[index] = val

    def __len__(self):
        """ Return the length of this production """
        return self._len

    def __repr__(self):
        """ Return a representation of this production """
        return "<P: " + repr(self._rhs) + ">"

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

        As an alternative to the '|' symbol, productions may also
        be separated by '>'. This indicates a priority ordering
        between the alternatives, so that the result tree is
        automatically reduced to the highest-priority alternative
        in case of ambiguity.

    """

    def __init__(self):

        self._nonterminals = { }
        self._terminals = { }

        # Dictionary of nonterminals indexed by integers < 0
        self._nonterminals_by_ix = { }
        # Dictionary of terminals indexed by integers > 0
        self._terminals_by_ix = { }

        self._nt_dict = { }
        self._root = None
        # Information about the grammar file
        self._file_name = None
        self._file_time = None

    @property
    def nt_dict(self):
        """ Return the raw grammar dictionary, Nonterminal -> [ Productions ] """
        return self._nt_dict

    @property
    def root(self):
        """ Return the root nonterminal for this grammar """
        return self._root

    @property
    def terminals(self):
        """ Return a dictionary of terminals in the grammar """
        return self._terminals

    @property
    def nonterminals(self):
        """ Return a dictionary of nonterminals in the grammar """
        return self._nonterminals

    @property
    def nonterminals_by_ix(self):
        """ Return a dictionary of nonterminals in the grammar indexed by integer < 0 """
        return self._nonterminals_by_ix

    @property
    def terminals_by_ix(self):
        """ Return a dictionary of terminals in the grammar indexed by integer > 0 """
        return self._terminals_by_ix

    def lookup(self, index):
        """ Look up a nonterminal or terminal by integer index """
        if index < 0:
            return self._nonterminals_by_ix.get(index, None)
        if index > 0:
            return self._terminals_by_ix.get(index, None)
        return None

    @property
    def num_nonterminals(self):
        """ Return the number of nonterminals in the grammar """
        return len(self._nonterminals)

    @property
    def num_terminals(self):
        """ Return the number of terminals in the grammar """
        return len(self._terminals)

    @property
    def num_productions(self):
        """ Return the total number of productions in the grammar,
            were each right hand side option is counted as one """
        return sum(len(pp) for pp in self._nt_dict.values())

    @property
    def file_name(self):
        """ Return the name of the grammar file, or None """
        return self._file_name

    @property
    def file_time(self):
        """ Return the timestamp of the grammar file, or None """
        return self._file_time

    def __getitem__(self, nt):
        """ Look up a nonterminal, yielding a list of (priority, production) tuples """
        return self._nt_dict[nt]

    def __str__(self):

        def to_str(plist):
            return " | ".join([str(p) for p in plist])

        return "".join([str(nt) + " → " + to_str(pp[1]) + "\n" for nt, pp in self._nt_dict.items()])

    def _make_terminal(self, name):
        """ Create a new Terminal instance within the grammar """
        # Override this to create custom terminals or add optimizations
        return Terminal(name)

    def _make_literal_terminal(self, name):
        """ Create a new LiteralTerminal instance within the grammar """
        # Override this to create custom terminals or add optimizations
        return LiteralTerminal(name)

    def _make_nonterminal(self, name, fname, line):
        """ Create a new Nonterminal instance within the grammar """
        # Override this to create custom nonterminals or add optimizations
        return Nonterminal(name, fname, line)

    def _write_binary(self, fname):
        """ Write grammar to binary file. Called after reading a grammar text file
            that is newer than the corresponding binary file, unless write_binary is False. """
        max_nt = 0
        with open(fname, "wb") as f:
            print("Writing binary grammar file {0}".format(fname))
            # Version header
            f.write("Reynir 00.00.00\n".encode('ascii')) # 16 bytes total
            num_nt = self.num_nonterminals
            # Number of terminals and nonterminals in grammar
            f.write(struct.pack("2I", self.num_terminals, num_nt))
            # Root nonterminal
            print("Root index is {0}".format(self.root.index))
            f.write(struct.pack("i", self.root.index))
            # Write nonterminals in numeric order, -1 first downto -N
            for ix in range(num_nt):
                nt = self.lookup(-1 - ix)
                plist = self[nt]
                f.write(struct.pack("I", len(plist)))
                # Write productions along with their priorities
                for prio, p in plist:
                    f.write(struct.pack("I", prio));
                    lenp = len(p)
                    f.write(struct.pack("I", lenp))
                    if lenp:
                        f.write(struct.pack(str(lenp)+"i", *p.prod))
        print("Writing of binary grammar file completed")
        print("num_terminals was {0}, num_nonterminals {1}".format(self.num_terminals, num_nt))

    def read(self, fname, verbose = False, write_binary = True):
        """ Read grammar from a text file. Set verbose = True to get diagnostic messages
            about unused nonterminals and nonterminals that are unreachable from the root.
            Set write_binary = False to avoid writing a fresh binary file if the
            grammar text file is newer than the existing binary file. """

        # Clear previous file info, if any
        self._file_time = self._file_name = None
        # Shortcuts
        terminals = self._terminals
        nonterminals = self._nonterminals
        grammar = self._nt_dict
        # The number of the current line in the grammar file
        line = 0

        # The nonterminal for which productions are being specified
        current_NT = None
        # The variants of the current nonterminal
        current_variants = []
        # Dictionary of variants, keyed by variant name
        # where the values are lists of variant options (strings)
        variants = { }
        current_line = ""

        def parse_line(s):

            s = s.strip()
            if not s:
                # Blank line: ignore
                return

            def _parse_rhs(nt_id, vts, s, priority):
                """ Parse a right-hand side sequence, eventually with relative priority
                    within the nonterminal """

                def _add_rhs(nt_id, rhs, priority = 0):
                    """ Add a fully expanded right-hand-side production to a nonterminal rule """
                    nt = nonterminals[nt_id]
                    if nt not in grammar:
                        # First production of this nonterminal
                        grammar[nt] = [ ] if rhs is None else [ (priority, rhs) ]
                        return
                    if rhs is None:
                        return
                    if rhs.is_empty:
                        # Adding epsilon production: avoid multiple ones
                        if any(p.is_empty for _, p in grammar[nt]):
                            return
                    # Append to the list of productions of this nonterminal
                    grammar[nt].append((priority, rhs))

                s = s.strip()
                if not s:
                    raise GrammarError("Invalid syntax for production", fname, line)

                tokens = s.split()

                # rhs is a list of tuples, one for each token, as follows:
                # (id, repeat, variants)
                rhs = []

                # vfree is a set of 'free variants', i.e. variants that
                # occur in the right hand side of the production but not in
                # the nonterminal (those are in vts)
                vfree = set()

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
                            # if vspec not in vts:
                            if vspec not in variants:
                                # raise GrammarError("Variant '{0}' not specified for nonterminal '{1}'".format(vspec, nt_id), fname, line)
                                raise GrammarError("Unknown variant '{0}'".format(vspec), fname, line)
                            if vspec not in vts:
                                # Free variant: add to set
                                vfree.add(vspec)

                    if r[0] in "\"'":
                        # Literal terminal symbol
                        if len(r) < 3 or r[0] not in r[2:]:
                            raise GrammarError("Invalid literal terminal {0}".format(r), fname, line)
                    else:
                        # Identifier of nonterminal or terminal
                        if not r.isidentifier():
                            raise GrammarError("Invalid identifier '{0}'".format(r), fname, line)
                    rhs.append((r, repeat, v))

                assert len(rhs) == len(tokens)

                # Generate productions for all variants

                def variant_values(vlist):
                    """ Returns a list of names with all applicable variant options appended """
                    if not vlist:
                        yield [ "" ]
                        return
                    if len(vlist) == 1:
                        for vopt in variants[vlist[0]]:
                            yield [ vopt ]
                        return
                    for v in variant_values(vlist[1:]):
                        for vopt in variants[vlist[0]]:
                            yield [ vopt ] + v

                # Make a list of all variants that occur in the
                # nonterminal or on the right hand side
                # Note: the list needs to be sorted for index predictability
                # between parses of the same grammar
                vall = vts + list(vfree)

                #for vval in variant_values(vall):
                for vval in variant_values(vall):
                    # Generate a production for every variant combination

                    # Calculate the nonterminal suffix for this variant
                    # combination
                    nt_suffix = "_".join(vval[vall.index(vx)] for vx in vts) if vts else ""
                    if nt_suffix:
                        nt_suffix = "_" + nt_suffix

                    result = Production(fname, line)
                    for r, repeat, v in rhs:
                        # Calculate the token suffix, if any
                        # This may be different from the nonterminal suffix as
                        # the token may have fewer variants than the nonterminal,
                        # and/or free ones that don't appear in the nonterminal.
                        suffix = "_".join(vval[vall.index(vx)] for vx in v) if v else ""
                        if suffix:
                            suffix = "_" + suffix
                        if r is None:
                            # Epsilon
                            n = None
                        elif r[0] in "'\"":
                            # Literal token
                            sym = r + suffix
                            if sym not in terminals:
                                terminals[sym] = self._make_literal_terminal(r + suffix)
                            n = terminals[sym]
                        else:
                            # Identifier for terminal or nonterminal
                            if r[0].isupper():
                                # Reference to nonterminal
                                if r + suffix not in nonterminals:
                                    nonterminals[r + suffix] = self._make_nonterminal(r + suffix, fname, line)
                                nonterminals[r + suffix].add_ref() # Note that the nonterminal has been referenced
                                n = nonterminals[r + suffix]
                            else:
                                # Identifier of terminal
                                if r + suffix not in terminals:
                                    terminals[r + suffix] = self._make_terminal(r + suffix)
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
                                new_nt = nonterminals[new_nt_id] = self._make_nonterminal(new_nt_id, fname, line)
                                new_nt.add_ref()
                                # Note that the Earley algorithm is more efficient on left recursion
                                # than middle or right recursion. Therefore it is better to generate
                                # Cx -> Cx C than Cx -> C Cx.
                                # First production: Cx C
                                new_p = Production(fname, line)
                                if repeat != '?':
                                    new_p.append(new_nt) # C* / C+
                                new_p.append(n) # C
                                _add_rhs(new_nt_id, new_p) # Default priority 0
                                # Second production: epsilon(*, ?) or C(+)
                                new_p = Production(fname, line)
                                if repeat == '+':
                                    new_p.append(n)
                                _add_rhs(new_nt_id, new_p) # Default priority 0
                            # Substitute the Cx in the original production
                            n = nonterminals[new_nt_id]

                        if n is not None:
                            result.append(n)

                    assert len(result) == len(rhs) or (len(rhs) == 1 and rhs[0] == (None, None, None))

                    nt_id_full = nt_id + nt_suffix

                    if len(result) == 1 and result[0] == nonterminals[nt_id_full]:
                        # Nonterminal derives itself
                        raise GrammarError("Nonterminal {0} deriving itself".format(nt_id_full), fname, line)
                    _add_rhs(nt_id_full, result, priority)

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
                if "_" in vname or not vname.isidentifier():
                    # Variant names must be valid identifiers without underscores
                    raise GrammarError("Invalid variant name '{0}'".format(vname), fname, line)
                v = v[1].split()
                for vopt in v:
                    if "_"  in vopt or not vopt.isidentifier():
                        # Variant options must be valid identifiers without underscores
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
                        cnt = self._make_nonterminal(nt_var, fname, line)
                        nonterminals[nt_var] = cnt
                        if self._root is None:
                            # Remember first nonterminal as the root
                            self._root = cnt
                            self._root.add_ref() # Implicitly referenced
                    if cnt not in grammar:
                        grammar[cnt] = [ ]

                sep = '|' # Default production separator
                if '>' in rule[1]:
                    # Looks like a priority specification between productions
                    if '|' in rule[1]:
                        raise GrammarError("Cannot mix '|' and '>' between productions", fname, line)
                    sep = '>'
                for priority, prod in enumerate(rule[1].split(sep)):
                    # Add the productions on the right hand side, delimited by '|' or '>'
                    _parse_rhs(current_NT, current_variants, prod, priority if sep == '>' else 0)

        # Main parse loop

        try:
            with open(fname, "r", encoding="utf-8") as inp:
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
            if verbose and not nt.has_ref:
                # Emit a warning message if verbose=True
                print ("Nonterminal {0} is never referenced in a production".format(nt))
                # raise GrammarError("Nonterminal {0} is never referenced in a production".format(nt), nt.fname(), nt.line())
            if nt not in grammar:
                raise GrammarError("Nonterminal {0} is referenced but not defined".format(nt), nt.fname, nt.line)
        for nt, plist in grammar.items():
            if len(plist) == 0:
                raise GrammarError("Nonterminal {0} has no productions".format(nt), nt.fname, nt.line)
            else:
                for _, p in plist:
                    if len(p) == 1 and p[0] == nt:
                        raise GrammarError("Nonterminal {0} produces itself".format(nt), p.fname, p.line)

        # Check that all nonterminals derive terminal strings
        agenda = [ nt for nt in nonterminals.values() ]
        der_t = set()
        while agenda:
            reduced = False
            for nt in agenda:
                for _, p in grammar[nt]:
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

        # Short-circuit nonterminals that point directly and uniquely to other nonterminals.
        # Becausee this creates a gap between the original grammar
        # and the resulting trees, we only do this for nonterminals with variants
        shortcuts = { } # Dictionary of shortcuts
        for nt, plist in grammar.items():
            if not "_" in nt.name:
                # 'Pure' nonterminal with no variants: don't shortcut
                continue
            if len(plist) == 1 and len(plist[0][1]) == 1 and isinstance(plist[0][1][0], Nonterminal):
                # This nonterminal has only one production, with only one nonterminal item
                target = plist[0][1][0]
                assert target != nt
                while target in shortcuts:
                    # Find ultimate destination of shortcut
                    assert target != shortcuts[target]
                    target = shortcuts[target]
                shortcuts[nt] = target

        # Go through all productions and replace the shortcuts with their targets
        for nt, plist in grammar.items():
            for _, p in plist:
                for ix, s in enumerate(p):
                    if isinstance(s, Nonterminal) and s in shortcuts:
                        # Replace the nonterminal in the production
                        target = shortcuts[s]
                        if verbose:
                            # Print informational message in verbose mode
                            print("Production of {2}: Replaced {0} with {1}"
                                .format(s, target, nt))
                        p[ix] = target

        # Now, after applying shortcuts, check that all nonterminals are reachable from the root
        unreachable = { nt for nt in nonterminals.values() }

        def _remove(nt):
            """ Recursively remove all nonterminals that are reachable from nt """
            unreachable.remove(nt)
            for _, p in grammar[nt]:
                for s in p:
                    if isinstance(s, Nonterminal) and s in unreachable:
                        _remove(s)

        _remove(self._root)

        if unreachable:
            if verbose:
                # Emit a warning message if verbose=True
                print ("Nonterminals {0} are unreachable from the root"
                    .format(", ".join([str(nt) for nt in unreachable])))
            # Simplify the grammar dictionary by removing unreachable nonterminals
            for nt in unreachable:
                del grammar[nt]
                del nonterminals[nt.name]

        # Reassign indices for nonterminals to avoid gaps in the
        # number sequence.
        # (Python is deliberately designed so that the order of dict
        # enumeration is not predictable; a straight numbering based
        # on nonterminals.values() will change with each run.)
        nt_keys_sorted = sorted(nonterminals.keys())
        self._nonterminals_by_ix = { -1 - ix : nonterminals[key] for ix, key in enumerate(nt_keys_sorted) }
        for key, nt in self._nonterminals_by_ix.items():
            nt.set_index(key)

        t_keys_sorted = sorted(terminals.keys())
        self._terminals_by_ix = { ix + 1 : terminals[key] for ix, key in enumerate(t_keys_sorted) }
        for key, t in self._terminals_by_ix.items():
            t.set_index(key)

#        for ix in range(len(nt_keys_sorted)):
#        nt_by_ix = { nt.index : nt for nt in nonterminals.values() }
#        max_ix = max(-index for index in nt_by_ix.keys())
#        ctr = 1
#        for ix in range(1, max_ix + 1):
#            if -ix in nt_by_ix:
#                nt_by_ix[-ix].set_index(-ctr)
#                ctr += 1
#
#        # Make a dictionary of nonterminals from the grammar
#        # keyed by the nonterminal index instead of its name
#        self._nonterminals_by_ix = { nt.index : nt for nt in nonterminals.values() }
#        # Same for terminals
#        self._terminals_by_ix = { t.index : t for t in terminals.values() }

        # Grammar successfully read: note the file name and timestamp
        self._file_name = fname
        self._file_time = datetime.fromtimestamp(os.path.getmtime(fname))

        if write_binary:
            # Check whether to write a fresh binary file
            fname = fname + ".bin" # By default Reynir.grammar.bin
            try:
                binary_file_time = datetime.fromtimestamp(os.path.getmtime(fname))
            except os.error:
                binary_file_time = None
            if binary_file_time is None or binary_file_time < self._file_time:
                # No binary file or older than text file: write a fresh one
                self._write_binary(fname)
