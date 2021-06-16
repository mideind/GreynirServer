#!/usr/bin/env python3

SEPARATOR = "\n\n"

accumulated = ""
filecnt = 0
limit = 1000000
f = "bit"
affix = 0
suff = ".txt"
with open('copper.txt', 'r') as copper:
    
    for line in copper:
        if not line: # Empty line between trees
            outfile = f + affix + suff
            with open(outfile, 'w') as chunk:
                chunk.write(accumulated)
            accumulated = ""
            if filecnt >= limit:
                limit += 1000000
                affix +=1

        accumulated += line
