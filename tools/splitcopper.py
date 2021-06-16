#!/usr/bin/env python3

SEPARATOR = "\n\n"

accumulated = ""
treecnt = 0
limit = 1000000
f = "bit"
affix = 0
suff = ".txt"

def gen_chunks(file):
    while True:
        data = file.read(1024)
        if not data:
            break
        yield data

    
for line in open("copper.txt"):
    if not line: # Empty line between trees
        treecnt +=1
        if treecnt % 500 == 0:
            print(f"{treecnt} sentences read")
        outfile = f + affix + suff
        with open(outfile, 'w') as chunk:
            chunk.write(accumulated)
        accumulated = ""
        if treecnt >= limit:
            limit += 1000000
            affix +=1

    accumulated += line
print(treecnt)
