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
        accumulated += line
        if filecnt >= limit:
            outfile = f + affix + suff
            with open(outfile, 'w') as chunk:
                chunk.write(accumulated)
            limit += 1000000
            accumulated = ""
            affix +=1
