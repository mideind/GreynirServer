
![Greynir](https://raw.githubusercontent.com/vthorsteinsson/Reynir/master/static/GreynirLogo242x100.png)

# Reynir

## Natural language processing for Icelandic

Try Reynir (in Icelandic) at [http://greynir.is](http://greynir.is)

*Reynir* is an experimental project that aims to extract processable information from
Icelandic text. It scrapes and tokenizes chunks of text from web pages
and parses the token streams according to a hand-written context-free grammar. The resulting
parse trees are disambiguated and finally processed to obtain statements of fact and relations
between stated facts.

Reynir is most effective for text that is objective and factual, i.e. has a relatively high
ratio of concrete concepts such as numbers, amounts, dates, person and entity names,
etc.

Reynir is innovative in its ability to parse and disambiguate text written in a grammatically
complex language, such as Icelandic, which does not lend itself easily to statistical
parsing methods. Reynir uses cases, genders, persons (1st, 2nd, 3rd), number (singular/plural)
and various verb modes applied appropriately to nouns, verbs, adjectives and prepositions to guide and
disambiguate parses. Its optimized Earley parser is fast and compact enough to make real-time
while-you-wait analysis of web pages, as well as bulk processing, feasible.

Reynir's goal is to "understand" text to a usable extent by parsing it into
structured trees that directly correspond to the original grammar.
These trees can then be further processed and acted upon by Python
functions associated with grammar nonterminals.

**Reynir is currently able to parse about *85%* of sentences** in a typical news article from the web,
and many well-written articles can be parsed completely. It has about 16.000 parsed articles
in its database, containing 500.000 parsed sentences.

Reynir may in due course be expanded, for instance:

* to make logical inferences from statements in its database;
* to find statements supporting or refuting a thesis; and/or
* to discover contradictions between statements.

## Implementation

Reynir is written in [Python 3](https://www.python.org/) except for its core
Earley parser module which is written in C++ and called
via [CFFI](https://cffi.readthedocs.org/en/latest/index.html).
Reynir runs on CPython and [PyPy](http://pypy.org/) with the latter being recommended.

Reynir works in stages, roughly as follows:

1. *Web scraper*, built on [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/)
  and [SQLAlchemy](http://www.sqlalchemy.org/) storing data
  in [PostgreSQL](http://www.postgresql.org/).
2. *Tokenizer*, relying on the BÍN database of Icelandic word forms for lemmatization and
  initial POS tagging.
3. *Parser*, using an improved version of the [Earley algorithm](http://en.wikipedia.org/wiki/Earley_parser)
  to parse text according to an unconstrained hand-written context-free grammar for Icelandic
  that may yield multiple parse trees (a parse forest) in case of ambiguity.
4. *Parse forest reducer* with heuristics to find the best parse tree.
5. *Information extractor* that maps a parse tree via its grammar constituents to plug-in
  Python functions.

Reynir has an embedded web server that allows the user to type in any URL
and have Reynir scrape it, tokenize it and display the result as a web page. The server runs
on the [Flask](http://flask.pocoo.org/) framework, implements WSGi and can for instance be
plugged into Gunicorn and Nginx.

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

The parser is an optimized C++ implementation of an Earley parser as enhanced by
[Scott and Johnstone](http://www.sciencedirect.com/science/article/pii/S0167642309000951),
referencing Tomita. It parses ambiguous grammars without restriction and
returns a compact Shared Packed Parse Forest (SPPF) of parse trees. If a parse
fails, it identifies the token at which no parse was available.

The Reynir scraper is typically run in a cron job once every 24 hours to extract articles automatically
from the web, parse them and store the resulting trees in a PostgreSQL database for further processing.

Scraper modules for new websites are plugged in by adding Python code to the `scrapers/` directory.
Currently, the `scrapers/default.py` module supports four popular Icelandic news sites as well
as the site of the Constitutional Council.

Processor modules can be plugged in to Reynir by adding Python code to the `processors/` directory.
The demo in `processors/default.py` extracts person names and titles form the processed text for
storage in a database table.

## File details

* `main.py` : WSGi application and main module for command-line invocation
* `settings.py` : Management of global settings and configuration data, obtained from `Reynir.conf`
* `scraper.py` : Web scraper, collecting articles from a set of pre-selected websites (roots)
* `scraperdb.py`: Wrapper for the scraper database via SQLAlchemy
* `tokenizer.py` : Tokenizer, designed as a pipeline of Python generators
* `dawgdictionary.py`: Handler for composite words using a compressed word form database
* `grammar.py` : Parsing of `.grammar` files, grammar constructs
* `baseparser.py` : Base class for parsers
* `bindb.py`: Interface to the BÍN database of Icelandic word forms
* `binparser.py` : Parser related subclasses for BÍN (Icelandic word) tokens
* `eparser.cpp` : Earley parser C++ module (header in `eparser.h`)
* `fastparser.py` : Python wrapper for `eparser.cpp` using CFFI
* `reducer.py` : Parse forest ambiguity resolver
* `processor.py`: Information extraction from parse trees
* `glock.py` : Utility class for global inter-process locking
* `ptest.py` : Parser test module
* `Reynir.conf` : Editable configuration file for the tokenizer and parser
* `Main.conf` : Various configuration data and preferences, included in `Reynir.conf`
* `Verbs.conf` : Editable lexicon of verbs, included in `Reynir.conf`
* `Reynir.grammar` : A context-free grammar specification for Icelandic
  written in BNF with extensions
  for repeating constructs (`*`, `+`) and optional constructs (`?`)
* `parser.py` : Older, pure-Python implementation of an Earley parser

## Copyright and licensing

The Reynir source code and associated files are
*copyright (C) 2015-2016 by Vilhjálmur Þorsteinsson*,
all rights reserved.

Please contact the author via GitHub for further information.
