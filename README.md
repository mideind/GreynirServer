
![Greynir](https://raw.githubusercontent.com/vthorsteinsson/Reynir/master/static/GreynirLogo242x100.png)

# Reynir

[![Join the chat at https://gitter.im/Greynir/Lobby](https://badges.gitter.im/Greynir/Lobby.svg)](https://gitter.im/Greynir/Lobby?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

## Natural language processing for Icelandic

Try Reynir (in Icelandic) at [https://greynir.is](https://greynir.is)

*Reynir* is a proof-of-concept project that aims to
**extract processable information from Icelandic text** and allow
**natural language querying** of that information.

Reynir scrapes and tokenizes chunks of text from web pages
and parses the token streams according to a **hand-written context-free grammar**
for the Icelandic language. The resulting parse forests are disambiguated using
scoring heuristics to find the best parse trees. The trees are then stored in a
database and processed by grammatical pattern matching modules to obtain statements
of fact and relations between stated facts.

Reynir is most effective for text that is objective and factual, i.e. has a relatively high
ratio of concrete concepts such as numbers, amounts, dates, person and entity names,
etc.

Reynir is innovative in its ability to parse and disambiguate text written in a
**grammatically complex language**, i.e. Icelandic, which does not lend itself easily
to statistical parsing methods. Reynir uses grammatical feature agreement (cases, genders,
persons, number (singular/plural), verb tenses, modes, etc.) to guide and disambiguate
parses. Its optimized Earley-based parser is fast and compact enough to make real-time
while-you-wait analysis of web pages, as well as bulk processing, feasible.

Reynir's goal is to "understand" text to a usable extent by parsing it into
structured, recursive trees that directly correspond to the original grammar.
These trees can then be further processed and acted upon by sets of Python
functions that are linked to grammar nonterminals.

**Reynir is currently able to parse about *86%* of sentences** in a typical news article from the web,
and many well-written articles can be parsed completely. It presently has over 100,000 parsed articles
in its database, containing 1.8 million parsed sentences.

Reynir supports natural language querying of its databases. Users can ask about person names, titles and
entity definitions and get appropriate replies. The HTML5 Web Speech API is supported to allow
queries to be **recognized from speech** in enabled browsers, such as recent versions of Chrome.

Reynir may in due course be expanded, for instance:

* to make logical inferences from statements in its database;
* to find statements supporting or refuting a thesis; and/or
* to discover contradictions between statements.

## Implementation

Reynir is written in [Python 3](https://www.python.org/) except for its core
Earley-based parser module which is written in C++ and called
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
6. *Article indexer* that transforms articles from bags-of-words to fixed-dimensional
  topic vectors using [Tf-Idf](http://www.tfidf.com/) and
  [Latent Semantic Analysis](https://en.wikipedia.org/wiki/Latent_semantic_analysis).
7. *Query processor* that allows natural language queries for entites in Reynir's database.

Reynir has an embedded web server that displays news articles recently scraped into its
databsae, as well as names of people extracted from those articles along with their titles.
The web UI enables the user to type in any URL and have Reynir scrape it, tokenize it and
display the result as a web page. Queries can also be entered via the keyboard or using voice
input. The server runs on the [Flask](http://flask.pocoo.org/) framework, implements WSGi and
can for instance be plugged into [Gunicorn](http://gunicorn.org/) and
[nginx](https://www.nginx.com/).

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
Thus, a single rule (e.g. `NounPhrase/case/gender → Adjective/case noun/case/gender`)
is automatically expanded into multiple rules (12 in this case, 4 cases x 3 genders) with
appropriate substitutions for right-hand-side tokens depending on their local variants.

The parser is an optimized C++ implementation of an Earley parser as enhanced by
[Scott and Johnstone](http://www.sciencedirect.com/science/article/pii/S0167642309000951),
referencing Tomita. It parses ambiguous grammars without restriction and
returns a compact Shared Packed Parse Forest (SPPF) of parse trees. If a parse
fails, it identifies the token at which no parse was available.

The Reynir scraper is typically run in a `cron` job every 30 minutes to extract
articles automatically from the web, parse them and store the resulting trees
in a PostgreSQL database for further processing.

Scraper modules for new websites are plugged in by adding Python code to the
`scrapers/` directory. Currently, the `scrapers/default.py` module supports
popular Icelandic news sites as well as the site of the Constitutional Council.

Processor modules can be plugged in to Reynir by adding Python code to the
`processors/` directory. The demo in `processors/default.py` extracts person
names and titles from parse trees for storage in a database table.

## File details

* `main.py` : WSGi web server application and main module for command-line invocation
* `settings.py` : Management of global settings and configuration data,
  obtained from `config/Reynir.conf`
* `scraper.py` : Web scraper, collecting articles from a set of pre-selected websites (roots)
* `scraperdb.py`: Wrapper for the scraper database via SQLAlchemy
* `tokenizer.py` : Tokenizer, designed as a pipeline of Python generators
* `dawgdictionary.py`: Handler for composite words using a compressed word form database
* `grammar.py` : Parsing of `.grammar` files, grammar constructs
* `baseparser.py` : Base class for parsers
* `incparser.py` : Incremental parsing of paragraphs and sentences from token streams
* `bindb.py`: Interface to the BÍN database of Icelandic word forms
* `binparser.py` : Parser related subclasses for BÍN (Icelandic word) tokens
* `eparser.cpp` : Earley parser core C++ module (header in `eparser.h`)
* `fastparser.py` : Python wrapper for `eparser.cpp` using CFFI
* `reducer.py` : Parse forest ambiguity resolver
* `processor.py`: Information extraction from parse trees
* `article.py` : Representation of an article through its life cycle
* `tree.py` : Representation of parse trees for processing
* `query.py` : Natural language query processor
* `vectors/builder.py` : Article indexer and LSA topic vector builder
* `config/Reynir.conf` : Editable configuration file for the tokenizer and parser
* `config/Main.conf` : Various configuration data and preferences, included in `Reynir.conf`
* `config/Prefs.conf` : Word form preference scores, included in `Reynir.conf`
* `config/Verbs.conf` : Lexicon of verbs, included in `Reynir.conf`
* `config/Abbrev.conf` : Lexicon of abbreviations, included in `Reynir.conf`
* `Reynir.grammar` : A context-free grammar specification for Icelandic
  written in BNF with extensions for repeating constructs (`*`, `+`)
  and optional constructs (`?`)
* `glock.py` : Utility class for global inter-process locking
* `fetcher.py` : Utility classes for fetching articles given their URLs
* `parser.py` : Older, pure-Python implementation of an Earley parser
* `utils/*.py` : Various utility programs

## Installation and setup

Limited installation and setup instructions can be
[found here](https://docs.google.com/document/d/1ywywjoOj5yas5QKjxLJ9Gqh-iNkfPae9-EKuES74aPU/edit?usp=sharing)
(in Icelandic).

## Install with Docker

Greynir can also be [built and run in Docker containers](https://github.com/vthorsteinsson/greynir-docker).

## Installation on OSx (Homebrew)
* Download and extract pypy3.3 (http://pypy.org/download.html#installing)
* `$ brew install postgresql (comes with contrib packages)`
* `$ pip3 install virtualenv`
* Clone this repo
* cd into repo
* `virtualenv -p /_your-pypy3-install-dir_/pypy3/bin/pypy3 venv`

### Postgres database setup
* `$ psql`
* `create user reynir with password 'reynir';`
* `create user notandi;` # Your username here
* `alter role notandi with superuser;`
* `create database bin with encoding 'UTF8' LC_COLLATE='is_IS.UTF-8' LC_CTYPE='is_IS.UTF-8' TEMPLATE=template0;`
* `\c bin` 
* `create table ord (stofn varchar(80), utg integer, ordfl varchar(16), fl varchar(16), ordmynd varchar(80), beyging varchar(24));`
* `copy ord from '/home/notandi/Reynir/resources/ord.csv' with (format csv, delimiter ';', encoding 'UTF8');`
* `create index ffx on ord(fl);`
* `create index ofx on ord(ordfl);`
* `create index oix on ord(ordmynd);`
* `create index sfx on ord(stofn);`

### Import external text and csv data
To load the BÍN lexicon and its supplemental text/csv files you need to run the import
and validation script found in `utils/external_data_validator.py`. This creates the
file `resources/ord.csv` which is copied into PostgreSQL as described above.

Put the downloaded BÍN files into the `Reynir/resources` directory. The names of these files
are currently assumed to be the following:

* `SHsnid.csv` (extracted from `SHsnid.csv.zip`)
* `obeyg.smaord.txt`
* `plastur.feb2013.txt`

## Copyright and licensing

Reynir/Greynir is *copyright (C) 2016 by Vilhjálmur Þorsteinsson*.

![GPLv3](https://raw.githubusercontent.com/vthorsteinsson/Reynir/master/static/GPLv3.png)

This set of programs is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any later
version.

This set of programs is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
A PARTICULAR PURPOSE. See the GNU General Public License for more details.

The full text of the GNU General Public License v3 is
[included here](https://github.com/vthorsteinsson/Reynir/blob/master/LICENSE.txt)
and also available here: https://www.gnu.org/licenses/gpl-3.0.html.

If you wish to use this set of programs in ways that are not covered under the
GPL v3 license, please contact the author.
