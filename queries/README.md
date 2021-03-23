# Greynir Query Modules

This directory contains Greynir's query modules, i.e. modules that handle Icelandic natural
language questions and commands. The current set of modules handles a wide range of queries
including many related to time, date, arithmetic, geography, locations, weather, etc.

Greynir currently supports two kinds of query modules: plain text modules that receive a
(mostly) unpreprocessed text string, and grammar modules, which provide their own context-free
grammar for the Greynir parser and operate on grammar non-terminals. Examples of both module
types can be found in the [`examples`](examples/) subdirectory:

* [`examples/plaintext.py`](examples/plaintext.py)
* [`examples/grammar.py`](examples/grammar.py)
