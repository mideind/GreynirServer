import json
import xml.etree.ElementTree as ET
import os
import json
import urllib.request
from urllib.parse import quote
from timeit import default_timer as timer

IFD_DIR = "ifd"

class Comparison():
    def __init__(self):
        self.ógreindar_setningar = 0 # Geymir fjölda setninga sem ekki tókst að greina
        self.réttar_setningar = 0 # Setningar þar sem öll mörk og allar lemmur eru réttar
        self.rangar_setningar = 0 # Setningar þar sem a.m.k. eitt rangt mark eða ein röng lemma fannst
        self.orð_vantar = 0 # Geymir heildarfjölda orða í setningum sem ekki tókst að greina
        self.rétt_orð = 0 # Bæði mark og lemma rétt
        self.röng_orð = 0 # Annaðhvort mark eða lemma rangt eða bæði
        self.LR = 0 #Réttar lemmur
        self.LW = 0 #Rangar lemmur
        self.MR = 0 # Rétt mörk
        self.MP = 0 # Hlutrétt mörk (rangur orðflokkur en rétt annað)
        self.MW = 0 # Röng mörk
        self.M_confmat = {} # Lykill er (x,y), x = mark frá Greyni, y = mark frá OTB. Gildi er tíðnin
        self.BÍN_MAP = { # TODO Eyða ef næ að reiða mig algerlega á mörk frá Greyni.
            "NFET": "en",
            "ÞFET": "eo",
            "ÞGFET": "eþ",
            "EFET": "ee",
            "NFFT": "fn",
            "ÞFFT": "fo",
            "ÞGFFT": "fþ",
            "EFFT": "ef",
            "FSB": "sf",
            "ESB": "se",
            "FVB": "vf",
            "EVB": "ve",
            "MST": "vm",
            "MST2": "vm",
            "MSTSB": "sm",
            "KK": "k",
            "ET": "e",
            "FT": "f",
            "ET2": "e",
            "FT2": "f",
            "KVK": "v",
            "HK": "h",
            "1P": "1",
            "2P": "2",
            "3P": "3",
            "NT": "n",
            "ÞT": "þ",
            "FH": "f",
            "VH": "v",
            "OSKH": "v", # Óskháttur, varpast í vh.
            "SAGNB": "s",
            "SAGNB2": "s",
            "NH": "n",
            "BH": "b",
            "LH": "l",
            "LHÞT": "þ",
            "ST": "e", # Stýfður boðháttur, sendi í eintölu
            "ST2": "e",
            "GM": "g",
            "MM": "m",
            "NF": "n",
            "ÞF": "o",
            "ÞGF": "þ",
            "EF": "e"
        }
        self.GrToOTB = { # TODO bæta við hér þegar búið að samræma mörk í Greyni.
            "kvk": "v",
            "kk": "k",
            "hk": "h",
            "nf": "n",
            "þf": "o",
            "þgf": "þ",
            "ef": "e",
            "et": "e",
            "ft": "f"
        }

    def lestur(self, skjal):
        print("\t***********************", skjal, "********************************")
        mypath = "http://localhost:5000/postag.api/v1?t="
        tree = ET.parse(skjal)
        root = tree.getroot()
        for sent in root.iter("s"):
            rétt_setning = True
            string = ""
            mörk_OTB = [word.get("type") for word in sent.iter("w")]
            lemmur_OTB = [word.get("lemma") for word in sent.iter("w")]
            orðalisti = [word.text for word in sent.iter("w")]
            setning = " ".join(orðalisti)
            setning = quote(setning)
            fullpath = mypath + setning
            #senda inn í httpkall og breyta í json-hlut
            try:
                with urllib.request.urlopen(fullpath) as response:
                    string = response.read().decode('utf-8')
            except urllib.error.HTTPError as e:
                print("Error {0} requesting URL {1}, skipping...".format(e, fullpath))
                continue
            json_obj = json.loads(string)
            all_words = json_obj["result"][0]
            #Tekst að greina setninguna?
            error = [y['x'] for y in all_words if "err" in y.keys()]
            if error:
                self.ógreindar_setningar += 1
                self.orð_vantar = self.orð_vantar + len(all_words)
                continue
            rétt_setning = True
            i = 0 # Index fyrir orðalistann.
            #print(*orðalisti)
            for word in all_words: # Komin á dict frá Greyni með öllum flokkunum.
                #print("====", word["x"], lemmur_OTB[i])
                lengd = max(len(word["x"].split(" ")), len(word["x"].split("-"))) #TODO breyta ef stuðningur við orð með bandstriki er útfærður.
                #print(word["x"], orðalisti[i])
                if word["x"] == "-": # Ef bandstrikið er greint sérstaklega
                    continue
                if lengd > 1: # Fleiri en eitt orð í streng Greynis
                    i = i + lengd - 1 # Enda á síðasta orðinu í tókanum
                    if i >= (len(orðalisti) - 1): #Getur gerst ef síðasta orð í streng
                        break
                elif not orðalisti[i].endswith(word["x"]): # orði skipt upp í Greyni en ekki OTB
                    if orðalisti[i] == "Bang-bang-bang": # Mjög ljótt sértilvik en erfitt að eiga við
                        i +=2
                        if i >= (len(orðalisti)-1):
                            break
                        continue
                    continue #Hægir mikið á öllu, e-r betri leið?
                #print(word["x"], word["k"])
                if word["k"] == "PUNCTUATION" or word["k"] == "UNKNOWN" or word["t"] == "no": # Einstaka tilvik
                    i +=1
                    #print("**** bæti einum við")
                    continue
                #Samanburður fer fram hér, safna tvenndum fyrir mörk í orðabók ásamt tíðni fyrir confusion matrix
                # Safna í allar tölfræðibreyturnar
                lemma_bool = self.sbrlemma(lemmur_OTB[i], word)
                mark_bool = self.sbrmark(mörk_OTB[i], word)
                if (lemma_bool and mark_bool): # Bæði mark og lemma rétt
                    self.rétt_orð += 1
                else:
                    self.röng_orð += 1
                    rétt_setning = False
                i+= 1
            if rétt_setning:
                self.réttar_setningar += 1
            else:
                self.rangar_setningar += 1

    def vörpun(self, word):
        # Skilar orðflokki og frekari greiningu.
        # k = tegund, x = upprunalegt orð, s = orðstofn, c = orðflokkur, b = beygingarform, t = lauf, v = gildi, f = flokkur í BÍN
        greining = []   # Geymir vörpun á marki orðsins sem er sambærileg marki í OTB
        # Varpa í réttan orðflokk
        if "PERCENT" in word["k"]:
            return "tp"
        elif "NUMBER" in word["k"] or "YEAR" in word["k"] or "ORDINAL" in word["k"] or "DATE" in word["k"] or "TIME" in word["k"]: #TODO sjá hvort þetta dugi.
            return "ta"
        elif "ENTITY" in word["k"]: #Fæ engar frekari upplýsingar. Breyti þegar hef samræmt mörk.
            return "nxxxxx"
        elif "CURRENCY" in word["k"]:
            # greining = orðfl.+kyn+tala+fall+sérnafn  
            uppl = word["t"].split("_") # [0]: orðfl, [1]: tala [2]: fall, [3]: kyn
            greining.append("n")
            if "gr" in uppl:
                uppl.remove("gr") #TODO get tekið út þegar samræmi mörkin.
            greining.append(self.GrToOTB[uppl[3]])
            greining.append(self.GrToOTB[uppl[1]])
            greining.append(self.GrToOTB[uppl[2]])
            greining.append("-s")
            return "".join(greining)
        elif "PERSON" in word["k"]:
            greining.append("n")
            uppl = word["t"].split("_") # [0]: person, [1]: fall, [2]: kyn
            if len(uppl) >= 3:
                kyn = uppl[2]
            elif "g" in word:
                kyn = word["g"]
            else:
                kyn = None # !!! Nota eitthvað kyn sem sjálfgefið?
            if kyn is not None:
                greining.append(self.GrToOTB[kyn])
            greining.append("e") #G.r.f. eintölu
            greining.append(self.GrToOTB[uppl[1]])
            greining.append("-m")
            return "".join(greining)
        elif "t" in word and "sérnafn" in word["t"]: # Samræma sérnöfnin í Greyni
            return "nxxn-s" #TODO eða -ö?
        if "c" in word:
            tegund = word["c"] #Sýnir orðflokk, á eftir að varpa í rétt.
        else:
            if word["t"].split("_")[0] == "no":
                tegund = word["t"].split("_")[-1]
            else:   # Ætti ekki að koma fyrir
                print("???", word["x"], word["k"], word["t"]) 
                if "b" in word:
                    print("b:", word["b"])
        if tegund in ["kvk","kk","hk"]: # Nafnorð
            greining.append("n")
            # greining = orðfl.+kyn+tala+fall+sérnafn
            greining.append(self.GrToOTB[tegund]) #kyn
            if "b" not in word or word["b"] == "-": # Skammstöfun, einstakir stafir, ...? Fæ uppl. frá Greyni
                uppl = word["t"].split("_") # [0]: orðfl, [1]: tala, [2]: fall, [3] kyn
                if len(uppl) < 3:
                    return "x" # Aðrar skammstafanir
                greining.append(self.GrToOTB[uppl[3]])
                greining.append(self.GrToOTB[uppl[1]])
                greining.append(self.GrToOTB[uppl[2]])
                return "".join(greining)
            talafall = word["b"].replace("gr", "")
            if talafall.endswith('2') or talafall.endswith('3'):
                talafall = talafall[:-1]
            greining.append(self.BÍN_MAP[talafall]) 
            if "gr" in word["b"]:
                greining.append("g")
            greining = "".join(greining)
        elif tegund == "lo":
            greining.append("l")
            #greining = orðfl+kyn+tala+fall+beyging+stig
            formdeildir = word["b"].split("-") # [0]: stig+beyging, [1]: kyn, [2]: fall+tala
            if len(formdeildir) == 2: #Raðtala; [0]: kyn, [1]: fall+tala
                greining.append(self.BÍN_MAP[formdeildir[0]])
                greining.append(self.BÍN_MAP[formdeildir[1]])
                greining.append("vf")
                return "".join(greining)
            greining.append(self.BÍN_MAP[formdeildir[1]])
            talafall = formdeildir[2].strip()
            if talafall.endswith('2') or talafall.endswith('3'):
                talafall = talafall[:-1]
            greining.append(self.BÍN_MAP[talafall])
            greining.append(self.BÍN_MAP[formdeildir[0]])
            greining = "".join(greining)
        elif tegund == "fn":
            # ábfn., óákv.ábfn., efn., óákv.fn., spfn.
            # greining = orðfl+undirflokkur+kyn+tala+fall
            greining.append("fx") # TODO því það vantar undirflokkun í Greyni
            formdeildir = word["b"].replace("fn_", "").replace("-", "_").split("_") # [0]: kyn, [1]: fall+tala
            talafall = formdeildir[1]
            if talafall.endswith('2') or talafall.endswith('3'):
                talafall = talafall[:-1]
            greining.append(self.BÍN_MAP[formdeildir[0]])
            greining.append(self.BÍN_MAP[talafall])
            greining = "".join(greining)
            #TODO skilgreina villu fyrir tilvfn.
            # TODO: Vantar undirflokkun. Fellur þetta mikið saman við orð úr öðrum flokkum?
        elif tegund == "pfn": #persónufornafn
            # greining = orðfl+undirfl+kyn/persóna+tala+fall
            greining.append("fpx") # TODO vantar persónu og kyn í Greyni
            # Fæ ekki persónu svo set x eins og er. Þarf að bæta því við í Greynismarkið.
            greining.append(self.BÍN_MAP[word["b"]])
            greining = "".join(greining)
        elif tegund == "abfn":
            greining.append("fpxe") # OTB greinir sem pfn.
            greining.append(self.BÍN_MAP[word["b"]])
            greining = "".join(greining)
        elif tegund == "gr":
            #greining = orðfl+kyn+tala+fall
            greining.append("g")
            formdeildir = word["b"].split("_") # [0]]: kyn, [1]: fall+tala
            greining.append(self.BÍN_MAP[formdeildir[0]])
            greining.append(self.BÍN_MAP[formdeildir[1]])
            greining = "".join(greining)
        elif tegund == "to":
            greining.append("tf")
            # greining = orðfl+kyn+tala+fall
            formdeildir = word["b"].split("_") # [0]]: kyn, [1]: fall+tala
            greining.append(self.BÍN_MAP[formdeildir[0]])
            talafall = formdeildir[1]
            if talafall.endswith('2') or talafall.endswith('3'): #tveim, þrem, ...
                talafall = talafall[:-1]
            greining.append(self.BÍN_MAP[talafall])
            greining = "".join(greining)
        elif tegund == "so":
            greining.append("s")
            formdeildir = word["b"].split("-") 
            if formdeildir[0] == "LHÞT": #lh.þt.
                # greining = orðfl+háttur+tala+fall f. lh.þt.
                # lh.þt.: [0]: háttur+tíð, [1]: beyging, [2]: kyn, [3]: fall+tala
                greining.append("sþ")
                talafall = formdeildir[3]
                if talafall.endswith('2') or talafall.endswith('3'):
                    talafall = talafall[:-1]
                greining.append(self.BÍN_MAP[talafall]) 
                greining = "".join(greining)
            elif formdeildir[0] == "LH": #lh.nt.
                # greining = orðfl+háttur+mynd
                # lh.nt.: [0]: háttur, [1]: tíð
                greining = "slx" #TODO mynd kemur hvergi fram, set x í staðinn.
            elif "SAGNB" in formdeildir[1]: # sagnbót. Bæði SAGNB og SAGNB2
                # greining = orðfl+háttur+mynd
                # sagnb.: [0]: mynd, [1]: háttur
                greining.append(self.BÍN_MAP[formdeildir[1]])
                greining.append(self.BÍN_MAP[formdeildir[0]])
                greining = "".join(greining)
            elif formdeildir[1] == "NH": #nh.
                # greining = orðfl+háttur+mynd(+"--þ" ef þátíð)
                # nh.: [0]: mynd, [1]: háttur, [2]: tíð ef til staðar(mundu, vildu, ...)
                greining.append(self.BÍN_MAP[formdeildir[1]])
                greining.append(self.BÍN_MAP[formdeildir[0]])
                if len(formdeildir) == 3: #þátíð
                    greining.append("--þ")
                greining = "".join(greining)
            elif formdeildir[1] == "BH": #bh.
                # greining = orðfl+háttur+mynd+persóna+tala+tíð
                # bh.: [0]: mynd, [1]: háttur, [2]: tala/stýfður
                greining.append(self.BÍN_MAP[formdeildir[1]])
                greining.append(self.BÍN_MAP[formdeildir[0]])
                greining.append("xxx") # TODO persóna, tala og tíð koma hvergi fram í BÍN eða Greyni. Set x í staðinn.
                greining = "".join(greining)
            elif formdeildir[0] == "OP": # ópersónulegar sagnir
                # fh. og vh.: [0]: "OP" [1]: mynd, [2]: háttur, [3]: tíð, [4]: persóna, [5]: tala
                #greining = orðfl+háttur+mynd+persóna+tala+tíð
                greining.append(self.BÍN_MAP[formdeildir[2]])
                greining.append(self.BÍN_MAP[formdeildir[1]])
                greining.append(self.BÍN_MAP[formdeildir[4]])
                greining.append(self.BÍN_MAP[formdeildir[5]])
                greining.append(self.BÍN_MAP[formdeildir[3]])
                greining = "".join(greining)
            else: #fh. og vh. eða skammstafaðar sagnir
                # greining = orðfl+háttur+mynd+persóna+tala+tíð
                # fh. og vh.: [0]: mynd, [1]: háttur, [2]: tíð, [3]: persóna, [4]: tala
                # Ath. óskháttur varpast í vh.
                if word["b"] == "-" and word["t"] == "so": #Undantekningartilvik
                    return "sxxxxx"
                greining.append(self.BÍN_MAP[formdeildir[1]])
                greining.append(self.BÍN_MAP[formdeildir[0]])
                greining.append(self.BÍN_MAP[formdeildir[3]])
                greining.append(self.BÍN_MAP[formdeildir[4]])
                greining.append(self.BÍN_MAP[formdeildir[2]])
                greining = "".join(greining)
        elif tegund == "ao":
            greining = "aa"
            # greining = orðfl+stig
            # TODO næ ekki að merkja upphrópanir.
            if word["b"] is "ao_MST":
                greining = "aam"
            elif word["b"] is "ao_EST":
                greining = "aae"
            else:
                greining = "aa"
        elif tegund == "fs":
            greining.append("a")
            formdeildir = word["t"].split("_")
            if len(formdeildir) == 1: #vantar stýringu, get tekið út þegar hef samræmt Greynismörk
                greining.append("x")
            else:
                greining.append(self.GrToOTB[formdeildir[1]]) #stýring
            greining = "".join(greining)
        elif tegund == "st":
            c = word["x"]
            if c in "sem" or c in "er": # tilvísunartengingar
                greining = "ct"
            else:
                greining = "c"
        elif tegund == "nhm":
            greining = "cn"
        elif tegund == "töl":
            greining = "to"
        else:
            print("Finn ekki greiningu:", tegund, word["k"], word["t"], word["x"])
            if "b" in word:
                print(word["b"])
        return greining

    def sbrlemma(self, lemma_OTB, word):
        #Fyllir út í self.tíðnibreytur
        if "s" in word:
            lemma_Gr = word["s"]
        else:
            lemma_Gr = word["x"]
        if lemma_Gr == lemma_OTB:
            self.LR += 1
            return True
        else:
            self.LW += 1
            return False

    def sbrmark(self, mark_OTB, word):
        # Fyllir út í self.tíðnibreytur fyrir mörkunarárangur
        mark_Gr = self.vörpun(word)
        tvennd = (tuple(mark_Gr), tuple(mark_OTB))
        if tvennd in self.M_confmat:
            self.M_confmat[tvennd] += 1
        else:
            self.M_confmat[tvennd] = 1
        if mark_Gr and mark_OTB and mark_Gr[0] == mark_OTB[0]: #Sami orðflokkur
            # Athuga hvort annað í markinu sé rétt
            # TODO nánari greining á villunni? Eða bara greina það handvirkt í stikkprufu?
            if mark_Gr == mark_OTB:
                self.MR += 1
                return True
            else:
                self.MP += 1
                return False
        else:
            self.MW += 1
            return False

    def prenta(self):
        # Prenta fyrst tíðni
        # Svo reikna nákvæmni, heimt, F-mælingu
        #Setningar
        print()
        print("******************** NIÐURSTÖÐUR *************************")
        print("Réttar setningar:", self.réttar_setningar)
        print("Rangar setningar", self.rangar_setningar)
        print("Ógreindar setningar:", self.ógreindar_setningar)
        if self.réttar_setningar == 0:
            SN, SH, SF = 0, 0, 0
        else:
            SN = self.réttar_setningar / (self.réttar_setningar + self.rangar_setningar)
            SH = self.réttar_setningar / (self.réttar_setningar + self.ógreindar_setningar)
            SF = (2 * SN * SH) / (SN + SH)
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(SN, SH, SF))
        print("")
        #Orð
        print("Rétt orð:", self.rétt_orð)
        print("Röng orð:", self.röng_orð)
        print("Orð vantar:", self.orð_vantar)
        if self.rétt_orð == 0:
            ON, OH, OH = 0, 0, 0
        else:
            ON = self.rétt_orð / (self.rétt_orð + self.röng_orð)
            OH = self.rétt_orð / (self.rétt_orð + self.orð_vantar)
            OF = (2 * ON * OH) / (ON + OH)
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(ON, OH, OF))
        print("")
        #Lemmur
        print("Réttar lemmur:", self.LR)
        print("Rangar lemmur:", self.LW)
        if self.LR == 0:
            LN, LH, LF = 0, 0, 0
        else:
            LN = self.LR / (self.LR + self.LW)# Nákvæmni lemmna; (réttar/(réttar+rangar))
            LH = self.LR / (self.LR + self.orð_vantar) # Heimt lemmna; (réttar/(réttar+vantar))
            LF = (2 * LN * LH) / (LN + LH) # F-measure lemmna
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(LN, LH, LF))
        print("")
        #Mörk
        print("Rétt mörk:", self.MR)
        print("Hlutrétt mörk (réttur orðflokkur):", self.MP)
        print("Röng mörk:", self.MW)
        if self.MR == 0:
            MN, MH, MF = 0, 0, 0
        else:
            MN = (self.MR + self.MP) / (self.MR + self.MP + self.MW)
            MH = self.MR / (self.MR + self.orð_vantar)
            MF = (2 * MN * MH) / (MN + MH) # F-measure lemmna
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(MN, MH, MF))

    def start(self):
        cwd = os.getcwd()
        xml_files = [x for x in os.listdir(cwd + "/" + IFD_DIR) if x.startswith("A") and x.endswith(".xml")]
        i = 1
        for each in xml_files:
            print("Skjal {} af 61".format(i))
            comp.lestur(cwd + "/" + IFD_DIR + "/" + each)
            i +=1
        comp.prenta()


if __name__ == "__main__":
    byrjun = timer()
    comp = Comparison()
    comp.start()
    lok = timer()
    print("Keyrslan tók {} sekúndur.".format(lok - byrjun))
