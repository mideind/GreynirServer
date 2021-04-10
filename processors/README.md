# Greynir Article Processors

This directory contains Greynir's article processor modules, i.e. modules that in one way
or another extract data from scraped articles. The current set of modules identifies and
gathers information about named entities, persons and locations, and stores it in the database.

Greynir currently supports two kinds of article processor modules: grammar processors, which
operate on sentence trees, and token processors, which operate on token streams.
