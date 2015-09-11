# Reynir

## Natural language processing for Icelandic

*Reynir* is an experimental project that aims to extract processable information from
Icelandic text on the web. It scrapes chunks of text from web pages, tokenizes them,
parses them according to a context-free grammar, disambiguates and analyzes the resulting parse
trees to obtain statements of fact and relations between stated facts.

Reynir will be most effective for text that is highly factual, i.e. has a relatively high
ratio of concrete concepts such as numbers, amounts, dates, person and entity names,
etc.

Reynir is innovative in its support for the complex grammar of Icelandic - using
cases, genders and number (singular/plural) applied respectively to nouns,
verbs, adjectives and prepositions to guide and disambiguate parses. Its optimized
Earley parser is fast and compact enough to make real-time while-you-wait analysis of
web pages, as well as bulk processing, feasible.

Reynir's goal is to "understand" text to a usable extent by parsing it into
structured and regular trees that directly correspond to the original grammar.
These trees can then be further processed and acted upon, for instance by Python
functions associated with grammar nonterminals.

If successful in its initial stages, Reynir may in due course be expanded, for instance:

* to make logical inferences from statements in its database;
* to find statements supporting or refuting a thesis; and/or
* to discover contradictions between statements.

## Implementation

Reynir is written in [Python 3](https://www.python.org/), apart from the web
front-end which has small amounts of JavaScript. It runs on CPython and
[PyPy](http://pypy.org/).

Reynir works in stages, roughly as follows:

1. *Web scraper*, built on [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/)
  and [SQLAlchemy](http://www.sqlalchemy.org/) storing data
  in [PostgreSQL](http://www.postgresql.org/).
2. *Tokenizer*, relying on the BÍN database of Icelandic word forms for initial POS tagging.
3. *Parser*, using an [Earley algorithm](http://en.wikipedia.org/wiki/Earley_parser) to
  parse text according to an unconstrained context-free grammar for Icelandic that may yield
  multiple parse trees (a parse forest) in case of ambiguity.
4. *Parse forest reducer* using heuristics to find the best parse tree.
5. *Information extractor* that maps a parse tree via its grammar constituents to plug-in
  Python functions.

Reynir contains a small web server that allows the user to type in any URL
and have Reynir scrape it, tokenize it and display the result as a web page. The server runs
on the [Flask](http://flask.pocoo.org/) framework.

Reynir uses the official BÍN ([Beygingarlýsing íslensks nútímamáls](http://bin.arnastofnun.is))
lexicon and database of Icelandic word forms to identify and tokenize words, and find their
grammatical roots and forms. The database has been downloaded from the official BÍN website and
stored in PostgreSQL.

The tokenizer divides text chunks into sentences and recognizes entities such as dates, numbers,
amounts and person names, as well as common abbreviations and punctuation.

Grammar rules are laid out in a separate text file, `Reynir.grammar`. The standard
[Backus-Naur form](http://en.wikipedia.org/wiki/Backus%E2%80%93Naur_Form) has been
augmented with repeat specifiers for right-hand-side tokens (`*` for 0..n instances,
`+` for 1..n instances, or `?` for 0..1 instances). Also, the grammar allows for
compact specification of rules with variants, for instance due to cases, numbers and genders.
Thus, a single rule (e.g. `NounPhrase/case/gender -> Adjective/case noun/case/gender`)
is automatically expanded into multiple rules (12 in this case, 4 cases x 3 genders) with
appropriate substitutions for right-hand-side tokens depending on their local variants.

The parser is an optimized Python implementation of an Earley parser as enhanced by
[Scott and Johnstone](http://www.sciencedirect.com/science/article/pii/S0167642309000951),
referencing Tomita. It parses ambiguous grammars without restriction and
returns a compact Shared Packed Parse Forest (SPPF) of parse trees. If a parse
fails, it identifies the token at which no parse was available.

## File details

* `main.py` : Web server
* `settings.py` : Management of global settings and configuration data, obtained from `Reynir.conf`
* `scraper.py` : Web scraper, collecting articles from a set of pre-selected websites (roots)
* `tokenizer.py` : Tokenizer, designed as a pipeline of Python generators
* `grammar.py` : Parsing of `.grammar` files, grammar constructs
* `parser.py` : Earley parser generic base classes
* `binparser.py` : Parser related subclasses for BIN (Icelandic word) tokens
* `reducer.py` : Parse forest ambiguity resolver
* `ptest.py` : Parser test module
* `Reynir.conf` : Editable configuration file for the tokenizer and parser
* `Verbs.conf` : Editable lexicon of verbs, included in `Reynir.conf`
* `Reynir.grammar` : A context-free grammar specification for Icelandic
  written in BNF with extensions
  for repeating constructs (`*`, `+`) and optional constructs (`?`)

## Copyright and licensing

The intent is to release Reynir under an open license once the code stabilizes. However, while
Reynir is still in early stages of development the code and associated files are
*copyright (C) 2015 by Vilhjalmur Thorsteinsson*, all rights reserved.
Please contact the author for further information.
