# Reynir

## Natural language processing for Icelandic

*Reynir* is an experimental project that aims to extract processable information from
Icelandic text on the web. It scrapes chunks of text from web pages, tokenizes them,
parses them and analyzes the resulting parse trees to obtain statements of fact
and relations between stated facts.

Reynir will be most effective for text that is highly factual, i.e. has a relatively high
ratio of concrete concepts such as numbers, amounts, dates, person and entity names,
etc.

If successful in its initial stages, Reynir may in due course be expanded, for instance:

* to make logical inferences from statements in its database;
* to find statements supporting or refuting a thesis; and/or
* to discover contradictions between statements.

## Implementation

Reynir is written in [Python 3.4](https://www.python.org/), apart from the web
front-end which has small amounts of JavaScript.

Reynir works in stages, roughly as follows:

1. *Web scraper*, built on [BeautifulSoup](http://www.crummy.com/software/BeautifulSoup/)
2. *Tokenizer*, relying on the BÍN database of Icelandic word forms
3. *Parser*, using an [Earley algorithm](http://en.wikipedia.org/wiki/Earley_parser) to
  parse text according to an unconstrained context-free grammar that may be ambiguous
4. *Parse forest analyzer* and information extractor

Reynir contains a small web server that allows the user to type in any URL
and have Reynir scrape it, tokenize it and display the result as a web page. The server runs
on the [Flask](http://flask.pocoo.org/) framework.

Reynir uses the official BÍN ([Beygingarlýsing íslensks nútímamáls](http://bin.arnastofnun.is)) database of
Icelandic word forms to identify and tokenize words, and find their potential meanings. The database
has been downloaded from the official BÍN webside and stored in PostgreSQL. It is accessed via the [Psycopg2](https://pypi.python.org/pypi/psycopg2) connector for Python.

The tokenizer divides text chunks into sentences and recognizes entities such as dates, numbers,
amounts and person names, as well as common abbreviations and punctuation.

## File details

* `main.py` : Web server
* `settings.py` : Management of global settings and configuration data
* `tokenizer.py` : Tokenizer, designed as a pipeline of Python generators
* `parser.py` : Earley parser, as
  enhanced by [Scott et al](http://www.sciencedirect.com/science/article/pii/S0167642309000951) referencing Tomita
* `ptest.py` : Parser test program
* `Reynir.conf` : Editable configuration file for the tokenizer and parser
* `Reynir.grammar` : A context-free grammar specification for Icelandic using
  [Backus-Naur format](http://en.wikipedia.org/wiki/Backus%E2%80%93Naur_Form) with extensions
  for repeating constructs (`*`, `+`) and optional constructs (`?`)

## Licensing

The intent is to release Reynir under a GNU license once the code stabilizes. However, while
Reynir is still in early stages of development the code is *copyright (C) 2015 by Vilhjalmur
Thorsteinsson*, all rights reserved.

