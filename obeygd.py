"""

Obeygd.py

Process list of undeclinable words and convert to CSV format

Author: Vilhjalmur Thorsteinsson 2015

Copy the result into PostgreSQL with the following statement:

\c bin
COPY ord FROM '/home/pi/ord/obeygd.csv' WITH (FORMAT CSV, DELIMITER ';', ENCODING 'utf8');

"""

import codecs

def run(infile, outfile):
    """ Read input file and output CSV """
    out = codecs.open(outfile, "w", "utf-8")
    with codecs.open(infile, "r", "latin-1") as inp:
        for li in inp:
            if li:
                li = li.strip()
                if not li.startswith("#"):
                    forms = li.split(u" ")
                    if forms:
                        word = forms[0]
                        for f in forms[1:]:
                            s = u"{0};{1};{2};{3};{4};{5}\n".format(
                                word, 0, f, u"ob", word, u"-"
                            )
                            out.write(s)
    out.close()

run("resources/obeyg.smaord.txt", "resources/obeygd.csv")
