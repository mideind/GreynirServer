#!/usr/bin/env python


import psycopg2
from iceaddr import iceaddr_lookup, placename_lookup
from geo import location_info
from processors.locations import LOCFL_TO_KIND

conn = psycopg2.connect(
    host="localhost", database="bin", user="reynir", password="reynir"
)
cur = conn.cursor()

###########################

cur.execute(
    "SELECT DISTINCT stofn, fl FROM ord WHERE fl='örn' OR fl='lönd' OR fl='göt' ORDER BY stofn"
)

res = cur.fetchall()
total = len(res)
no_match = 0
print("Total {0} unique örnefni".format(total))


for r in res:
    word = r[0]
    fl = r[1]

    if not word[:1].isupper():
        continue

    i = location_info(word, LOCFL_TO_KIND[fl])

    if i.get("country") is None and i.get("continent") is None:
        addr = iceaddr_lookup(word, limit=1)
        if len(addr) == 0:
            print("{0} - {1}".format(word, fl))
            no_match += 1

print("Not found: {0} / {1} ".format(no_match, total))

# print("{0} {1} {2}".format(word, ordfl, "örn"))

# addrs = iceaddr_lookup(word, limit=1)
# print(word)
# pns = placename_lookup(word)

# #print(pns)
# if pns:
# 	print(pns)
# if len(addrs) == 0 and len(pns) == 0:
# # 	print("NOT FOUND: " + street)
# loc = []
# if len(pns):
# 	loc.append('örn')
# if len(addrs):
# 	loc.append('göt')


# if "örn" in loc:
# 	continue

# if len(loc) == 0:
# 	# print("{0} NOT FOUND ANYWHERE".format(word))
# 	continue

# # OK, found in örnefnaskra
# print("{0} {1} {2}".format(word, ordfl, "göt"))

# # Check if word exists in more than one fl
# cur.execute("SELECT DISTINCT fl FROM ord WHERE stofn=%s", (word,))
# q = cur.fetchall()
# if len(q) > 1:
# 	print("\tCats in BÍN: " +  str(q))


# if len(loc) == 0:
# 	print("Örnefni {0} NOT FOUND".format(word, str(loc)))
# elif "göt" in loc:
# 	print("Örnefni {0} could be STREET".format(word))

# Check if word exists in more than one fl
# cur.execute("SELECT DISTINCT fl FROM ord WHERE stofn=%s", (word,))
# q = cur.fetchall()
# if len(q) > 1:
# 	print("\tCats in BÍN: " +  str(q))


###########################

cur.close()
conn.close()
