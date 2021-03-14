#!/usr/bin/env python
# type: ignore

import os
import sys
from timeit import default_timer as timer
import subprocess

# Hack to make this Python program executable from the tools subdirectory
basepath, _ = os.path.split(os.path.realpath(__file__))
_TOOLS = os.sep + "tools"
if basepath.endswith(_TOOLS):
    basepath = basepath[0:-len(_TOOLS)]
    sys.path.append(basepath)

from settings import Settings
from db import SessionContext
from treeutil import TreeUtility as tu

Settings.read(os.path.join(basepath, "config", "Greynir.conf"))
Settings.DEBUG = False
TEXTI = 'þróunarsafn_texti.txt'
SBR = 'þróunarsafn.txt'
SKIPUN = './EVALB/evalb -p ./stillingar.prm' # Þróunarsafnið kemur fyrst, svo þáttun til að prófa

class Comparison():
    def start(self):
        # Sækja setningar úr þróunarmálheild
        print("Sæki setningar...\n")
        setningar = self.fá_setningar()
        print("Komið! Sæki þáttun... \n")
        # Fá þáttun frá Greyni á svigaformi sem búið er að hreinsa
        þáttun = self.fá_þáttun(setningar) # Listi af þáttuðum setningum sem búið er að laga að Evalb-staðli
        print("Komið! Sæki niðurstöður í Evalb...\n")
        # Fá niðurstöður frá Evalb
        self.niðurstöður(þáttun)
        print("Allt komið!")

    def fá_þáttun(self, setningar):
        þáttun = []
        for setning in setningar:
            with SessionContext(read_only = True) as session:
                pgs, stats = tu.parse_text_to_bracket_form(session, setning)
            if len(pgs[0]) > 1: # Greint sem margar setningar, vil sameina
                allar = ""
                for pg in pgs:
                    for þáttuð_setning in pg:
                        allar = allar + þáttuð_setning
                hrein_þáttun = self.forvinnsla(allar)
                þáttun.append(hrein_þáttun)
                continue
            for pg in pgs:
                if not pg[0]: # Tóm setning
                    þáttun.append("(M (S x))") # Default grunngreining setningar -- breytt til að Evalb þoli!
                    continue
                for þáttuð_setning in pg:
                    # Hreinsa setningu
                    hrein_þáttun = self.forvinnsla(þáttuð_setning)
                    þáttun.append(hrein_þáttun)
        return þáttun

    def forvinnsla(self, þáttuð_setning):
        # Eyða 'ekki' - passa að bara ef heilt orð og er ao! Ath. hvort hluti af margorða lið
        # Finna margorða liði, setja undirstrik á milli ef það vantar
        # Færa síðasta svigann að hinum - breytir það einhverju? - s.s. ef finn ') )' breyta í "))" - fínt lokaskref
        # G.r.f. að Evalb eyði tómum liðum og því öllu - það er talað um það í skjöluninni.
        frasi = []
        hreinsuð_setning = ""
        liðir = Stack()
        # TODO eyða tvöföldum bilum eins oft og ég finn - lúppa?
        #þáttuð_setning.replace("  ", " ") # Eyða tvöföldu bili eftir að greinarmerki hafa verið tekin út
        for orð in þáttuð_setning.split(" "):
            if not orð: # Ef er með margföld bil - ný nálgun
                continue
            if "(" in orð: # Byrja nýjan lið
                liðir.push(orð)
                liður = orð.replace("(", "")
                if not frasi:
                    hreinsuð_setning = hreinsuð_setning + orð + " "
                else:
                    orðin = "_".join(frasi)
                    hreinsuð_setning = hreinsuð_setning + orðin + " " + orð + " "
                    frasi = []
            elif ")" in orð: # Lið lýkur; þarf að telja hve mörgum
                orðið = orð.replace(")", "")
                frasi.append(orðið)
                svigar = orð.count(")")
                orðin = "_".join(frasi)
                frasi = []
                # Telja svigana, poppa í samræmi við það og bæta líka við hreinsuðu setninguna
                hreinsuð_setning = hreinsuð_setning + orðin + orð[(-svigar):] + " "
                # Sæki orðið
                for x in range(svigar):
                    liður = liðir.pop()
            else:
                if "AO" in liður and (orð is "ekki" or orð is "Ekki"):
                    continue # Vil ekki safna lið
                else:
                    frasi.append(orð)
        #print(þáttuð_setning)
        #print("\t"+hreinsuð_setning)
        hreinsuð_setning = hreinsuð_setning.replace(") )", "))") # Lok setningar
        return hreinsuð_setning

    def niðurstöður(self, þáttun):
        # Byrjar á að skrifa þáttaðar setningar í skjal
        # kallar svo á skel fyrir prófunarmálheildina og útkomuna
        útkomuskjal = "útkoma.txt"
        with open(útkomuskjal, 'w+') as útkoma: # TODO ætti að vera 'w+'
            for setning in þáttun:
                if not setning:
                    continue
                else:
                    útkoma.write(setning+"\n")
        # Senda í skel
        evalb_niðurstöður = "evalb_niðurstöður.txt"
        heilskipun = SKIPUN + " ./{} ./{} > ./{}".format(SBR, útkomuskjal, evalb_niðurstöður)
        print("Sendi í Evalb!")
        skil = subprocess.Popen([heilskipun], shell=True, stdout=subprocess.PIPE).communicate()[0]
        print(skil)

    def fá_setningar(self):
        # Les setningar úr þróunarmálheild
        setningar = []
        with open(TEXTI, 'r') as þróun:
            for line in þróun:
                setningar.append(line.strip())
        return setningar

class Stack:

    def __init__(self):
        self.items = []

    def isEmpty(self):
        return self.items == []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return self.items.pop()

    def peek(self):
        return self.items[len(self.items)-1]

    def size(self):
        return len(self.items)

if __name__ == "__main__":
    byrjun = timer()
    comp = Comparison()
    comp.start()
    lok = timer()
    liðið = lok - byrjun
    print("")
    print("Keyrslan tók {:f} sekúndur, eða {:f} mínútur.".format(liðið, (liðið / 60.0)))

