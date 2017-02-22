import json
import xml.etree.ElementTree as ET
import os
import json
import urllib.request
from urllib.parse import quote
from timeit import default_timer as timer

IFD_DIR = "ifd" 
# GREINARMERKI = {"!", "(", ")", ",", "-", ".", "...", "/", ":", ";", "?", "[", "]", "«", "»"} # Öll greinarmerki sem koma fyrir í OTB
VINSTRI_GREINARMERKI = "([„«#$€<"
MIÐJA_GREINARMERKI = '"*&+=@©|—'
HÆGRI_GREINARMERKI = ".,:;)]!%?“»”’…°>–"
EKKI_GREINARMERKI = "-/'~‘\\"
GREINARMERKI = VINSTRI_GREINARMERKI + MIÐJA_GREINARMERKI + HÆGRI_GREINARMERKI + EKKI_GREINARMERKI
FLOKKAR = {
    "PERCENT": "tp", 
    "NUMBER": "ta", 
    "YEAR": "ta", 
    "ORDINAL": "ta", 
    "DATE": "ta",
    "TIME": "ta",
    "TIMESTAMP": "ta",
    "ENTITY": "e"
    }
BÍN_MAP = {
    "NFET": "en",
    "NFETgr": "eng",
    "NFET2": "en",
    "NFETgr2": "eng",
    "NFET3": "en",
    "NFETgr3": "eng",
    "ÞFET": "eo",
    "ÞFETgr": "eog",
    "ÞFET2": "eo",
    "ÞFETgr2": "eog",
    "ÞFET3": "eo",
    "ÞFETgr3": "eog",
    "ÞGFET": "eþ",
    "ÞGFETgr": "eþg",
    "ÞGFET2": "eþ",
    "ÞGFETgr2": "eþg",
    "ÞGFET3": "eþ",
    "ÞGFETgr3": "eþg",
    "EFET": "ee",
    "EFETgr": "eeg",
    "EFET2": "ee",
    "EFETgr2": "eeg",
    "EFET3": "ee",
    "EFETgr3": "eeg",
    "NFFT": "fn",
    "NFFTgr": "fng",
    "NFFT2": "fn",
    "NFFTgr2": "fng",
    "NFFT3": "fn",
    "NFFTgr3": "fng",
    "ÞFFT": "fo",
    "ÞFFTgr": "fog",
    "ÞFFT2": "fo",
    "ÞFFTgr2": "fog",
    "ÞFFT3": "fo",
    "ÞFFTgr3": "fog",
    "ÞGFFT": "fþ",
    "ÞGFFTgr": "fþg",
    "ÞGFFT2": "fþ",
    "ÞGFFTgr2": "fþg",
    "ÞGFFT3": "fþ",
    "ÞGFFTgr3": "fþg",
    "EFFT": "ef",
    "EFFTgr": "efg",
    "EFFT2": "ef",
    "EFFTgr2": "efg",
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
GrToOTB = {
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
        self.GR = 0 # Rétt greinarmerki (kemur inn í útreikninga fyrir lemmur og mörk)
        self.GW = 0 # Röng greinarmerki. Þau geta ekki verið hlutrétt
        #self.M_confmat = {} # Lykill er (x,y), x = mark frá Greyni, y = mark frá OTB. Gildi er tíðnin. TODO útfæra confusion matrix f. niðurstöður

    def lestur(self, skjal):
        print("*******************", skjal, "**************************")
        mypath = "http://localhost:5000/postag.api/v1?t="
        tree = ET.parse(skjal)
        root = tree.getroot()
        for sent in root.iter("s"):
            rétt_setning = True
            string = ""
            mörk_OTB = [word.get("type") for word in sent.iter()]
            lemmur_OTB = [word.get("lemma") for word in sent.iter()]
            orðalisti = [word.text.strip() for word in sent.iter()]
            setning = ""
            bil = True # Bil á undan núverandi staki
            for item in orðalisti:
                if not item: # Tómur hnútur fremst/aftast í setningu
                    continue
                elif item in VINSTRI_GREINARMERKI: # Ekkert bil á eftir
                    if bil:
                        setning = setning + " " + item
                    else:
                        setning = setning + item
                    bil = False # Ekkert bil á eftir þessu
                elif item in MIÐJA_GREINARMERKI: # Hvorki bil á undan né á eftir
                    setning = setning + item 
                    bil = False
                elif item in HÆGRI_GREINARMERKI: # Ekki bil á undan
                    setning = setning + item
                    bil = True
                else: # Venjulegt orð, bil á undan og á eftir nema annað komi til
                    if bil:
                        setning = setning + " " + item
                    else:
                        setning = setning + item
                    bil = True
            #print(setning)
            setning = quote(setning.strip())
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
                self.orð_vantar = self.orð_vantar + len(all_words) # Ath. þetta tekur greinarmerkin með.
                continue
            i = 0 # Index fyrir orðalistann.
            for word in all_words: # Komin á dict frá Greyni með öllum flokkunum.
                #print(word["x"], orðalisti[i])
                if not orðalisti[i]: # Tómur hnútur fremst/aftast í setningu
                    #print("Rakst á tóman hnút")
                    i += 1
                if  "x" in mörk_OTB[i]: # Ógreint orð í OTB, óþarfi að taka með í niðurstöðum
                    i += 1
                    if i >= (len(orðalisti) - 1): #Getur gerst ef síðasta orð í streng
                        break
                    continue
                #print(word["x"]+"*"+orðalisti[i]+"*"+str(lemmur_OTB[i])+"*"+str(mörk_OTB[i]))
                if lemmur_OTB[i] is None: # Greinarmerki
                    #print("1, díla við greinarmerki")
                    mörkun_bool = self.sbrGreinarmerki(mörk_OTB[i], word)
                    if mörkun_bool:
                        #print("2, fann mörkun greinarmerkis")
                        self.GR += 1
                    else:
                        #print("3, fann ranga mörkun greinarmerkis")
                        self.GW += 1
                        rétt_setning = False
                else:
                    #print("4, díla við orð")
                    lengd = max(len(word["x"].split(" ")), len(word["x"].split("-"))) #TODO breyta ef stuðningur við orð með bandstriki er útfærður.
                    #print("lengd:", str(lengd))
                    if word["x"] == "-": # Ef bandstrikið er greint sérstaklega
                        #print("10, orðið er bandstrik")
                        continue
                    if lengd > 1: # Fleiri en eitt orð í streng Greynis # TODO breyta þegar set dict með MWE inn
                        #print("11, fleiri en eitt orð í Greyni")
                        i = i + lengd - 1 # Enda á síðasta orðinu í tókanum # TODO atviksliðir. Skgr. sértilvik? Amk fyrir algengustu. skoða main.conf
                        #print("Nú hef ég {}".format(orðalisti[i]))
                        if i >= (len(orðalisti) - 1): #Getur gerst ef síðasta orð í streng
                            #print("12, síðasta orð í streng")
                            break
                        if orðalisti[i] == "Tse-Tung" or orðalisti[i] == "Peale-plani": # Ljót sértilvik
                            continue
                    elif not orðalisti[i].endswith(word["x"]): # orði skipt upp í Greyni en ekki OTB
                        #print("5, orði skipt upp í Greyni en ekki OTB")
                        if orðalisti[i] == "Bang-bang-bang": # Mjög ljótt sértilvik en erfitt að eiga við
                            i +=2
                            if i >= (len(orðalisti)-1):
                                break
                            continue
                        continue #Hægir mikið á öllu, e-r betri leið?
                    #print(word["x"], word["k"])
                    if ("k" in word and word["k"] == "PUNCTUATION" or word["k"] == "UNKNOWN") or ("t" in word and word["t"] == "no"): # Einstaka tilvik. PUNCTUATION hér er t.d. bandstrik sem OTB heldur í orðum en Greynir greinir sem stakt orð
                        #print("6, eitthvað skrýtið,", word["k"], word["x"]) # Skammstafanir sem ræð ekki við og annað.
                        i +=1
                        continue
                    #Samanburður fer fram hér, safna tvenndum fyrir mörk í orðabók ásamt tíðni fyrir confusion matrix
                    # Safna í allar tölfræðibreyturnar
                    lemma_bool = self.sbrlemma(lemmur_OTB[i], word)
                    mark_bool = self.sbrmark(mörk_OTB[i], word)
                    if (lemma_bool and mark_bool): # Bæði mark og lemma rétt
                        #print("7, fæ rétt orð")
                        self.rétt_orð += 1
                    else:
                        #print("8, fæ rangt orð")
                        self.röng_orð += 1
                        rétt_setning = False # A.m.k. eitt rangt mark eða ein röng lemma finnst í setningu.
                #print("9, neðst í lúppu")
                i += 1
            if rétt_setning:
                self.réttar_setningar += 1
            else:
                self.rangar_setningar += 1

    def vörpun(self, word):
        # Skilar orðflokki og frekari greiningu.
        # k = tegund, x = upprunalegt orð, s = orðstofn, c = orðflokkur, b = beygingarform, t = lauf, v = gildi, f = flokkur í BÍN
        greining = []   # Geymir vörpun á marki orðsins sem er sambærileg marki í OTB
        # Varpa í réttan orðflokk
        if word["k"] in FLOKKAR: 
            return FLOKKAR[word["k"]]
        elif "CURRENCY" in word["k"]:
            # greining = orðfl.+kyn+tala+fall+sérnafn  
            if "b" in word:
                print("CURRENCY:", word["b"])
            uppl = word["t"].split("_") # [0]: orðfl, [1]: tala [2]: fall, [3]: kyn
            greining.append("n") # orðflokkur
            # TODO breyta í BÍN mörk! Hvað kemur þar fram?
            if "gr" in uppl:
                uppl.remove("gr") #TODO get tekið út þegar samræmi mörkin. Sértilvik.
            greining.append(GrToOTB[uppl[3]]) # kyn
            greining.append(GrToOTB[uppl[1]]) # tala
            greining.append(GrToOTB[uppl[2]]) # fall
            greining.append("-s") # sérnafn
            return "".join(greining)
        elif "PERSON" in word["k"]:
            # TODO hvað sýnir BÍN?
            greining.append("n") # orðflokkur
            uppl = word["t"].split("_") # [0]: person, [1]: fall, [2]: kyn
            if len(uppl) >= 3:
                kyn = uppl[2] # kyn
            elif "g" in word:
                kyn = word["g"]
            else:
                kyn = None # !!! Nota eitthvað kyn sem sjálfgefið?
            if kyn is not None:
                greining.append(GrToOTB[kyn])
            greining.append("e") # tala - G.r.f. eintölu
            greining.append(GrToOTB[uppl[1]]) # fall
            greining.append("-m")
            return "".join(greining)
        elif "t" in word and "sérnafn" in word["t"]: # Samræma sérnöfnin í Greyni
            #if "b" in word:
                #print("Sérnafn???", word["b"]) # TODO tékka hvort "-s" kemur fram alls staðar
            return "nxxn-s" #TODO eða -ö?
        if "c" in word:
            tegund = word["c"] #Sýnir orðflokk, á eftir að varpa í rétt.
        else:
            if "t" not in word: # Skrýtnar skammstafanir, TODO ætti að lagast þegar fleiri skammstöfunum hefur verið bætt við Main.conf
                return "x"
            elif word["t"].split("_")[0] == "no": # Ekkert BÍN-mark. Stafsetningarvillur og annað
                #print("Hvað gerist hér??", word["t"], word["x"]) 
                tegund = word["t"].split("_")[-1]
                if "b" in word:
                    print("\tb:", word["b"])
            else:   # Ætti ekki að koma fyrir
                print("???", word["x"], word["k"], word["t"]) 
                if "b" in word:
                    print("b:", word["b"])
        if tegund in ["kvk","kk","hk"]: # Nafnorð
            greining.append("n") # orðflokkur
            # greining = orðfl.+kyn+tala+fall(+greinir)(+sérnafn)
            greining.append(GrToOTB[tegund]) #kyn
            if "b" not in word or word["b"] == "-": # Skammstöfun, einstakir stafir, ...? Fæ uppl. frá Greyni
                uppl = word["t"].split("_") # [0]: orðfl, [1]: tala, [2]: fall, [3] kyn
                if len(uppl) < 3:
                    return "x" # Aðrar skammstafanir
                greining.append(GrToOTB[uppl[1]]) # tala
                greining.append(GrToOTB[uppl[2]]) # fall
                return "".join(greining)
            greining.append(BÍN_MAP[word["b"]])  #tala+fall
            greining = "".join(greining)
        elif tegund == "lo": # Lýsingarorð
            greining.append("l")
            #greining = orðfl+kyn+tala+fall+beyging+stig
            formdeildir = word["b"].split("-") # [0]: stig+beyging, [1]: kyn, [2]: fall+tala
            if len(formdeildir) == 2: #Raðtala; [0]: kyn, [1]: fall+tala
                greining.extend(self.kyntalafall(formdeildir))
                greining.append("vf")
                return "".join(greining)
            greining.append(BÍN_MAP[formdeildir[1]])
            greining.append(BÍN_MAP[formdeildir[2].strip()]) # meiru, fleiru, fleirum
            greining.append(BÍN_MAP[formdeildir[0]])
            greining = "".join(greining)
        elif tegund == "fn": # Fornöfn
            # ábfn., óákv.ábfn., efn., óákv.fn., spfn.
            # greining = orðfl+undirflokkur+kyn+tala+fall
            greining.append(self.undirflokkun(word))
            formdeildir = word["b"].replace("fn_", "").replace("-", "_").split("_") # [0]: kyn, [1]: fall+tala
            greining.extend(self.kyntalafall(formdeildir))
            greining = "".join(greining)
            #TODO skilgreina villu fyrir tilvfn.
            # TODO: Vantar undirflokkun. Fellur þetta mikið saman við orð úr öðrum flokkum?
        elif tegund == "pfn": #persónufornöfn
            # greining = orðfl+undirfl+kyn/persóna+tala+fall
            greining.append(self.pk(word)) # orðfl.+ndirfkyn/persóna
            greining.append(BÍN_MAP[word["b"]]) # tala+fall
            greining = "".join(greining)
        elif tegund == "abfn": # Afturbeygð fornöfn
            greining.append("fpxe") # OTB greinir sem pfn. með kyni. Ég hef ekki.
            greining.append(BÍN_MAP[word["b"]]) # fall
            greining = "".join(greining)
        elif tegund == "gr": # Greinir
            #greining = orðfl+kyn+tala+fall
            # TODO skoða reglur
            greining.append("g")
            formdeildir = word["b"].split("_") # [0]]: kyn, [1]: fall+tala
            greining.extend(self.kyntalafall(formdeildir))
            greining = "".join(greining)
        elif tegund == "to": # Önnur töluorð
            greining.append("tf")
            # greining = orðfl+kyn+tala+fall
            formdeildir = word["b"].split("_") # [0]]: kyn, [1]: fall+tala
            greining.extend(self.kyntalafall(formdeildir))
            greining = "".join(greining)
        elif tegund == "so": # Sagnorð
            greining.append("s") # orðflokkur
            formdeildir = word["b"].split("-") 
            if formdeildir[0] == "LHÞT": #lh.þt.
                # greining = orðfl+háttur+tala+fall
                # lh.þt.: [0]: háttur+tíð, [1]: beyging, [2]: kyn, [3]: fall+tala
                greining.append("þ") # háttur
                greining.append(BÍN_MAP[formdeildir[3]]) #tala+fall
                greining = "".join(greining)
            elif formdeildir[0] == "LH": #lh.nt.
                # greining = orðfl+háttur+mynd
                # lh.nt.: [0]: háttur, [1]: tíð
                greining = "slg" #TODO mynd kemur hvergi fram, set g í staðinn. "m" er alger undantekning.
            elif "SAGNB" in formdeildir[1]: # sagnbót. Bæði SAGNB og SAGNB2
                # greining = orðfl+háttur+mynd
                # sagnb.: [0]: mynd, [1]: háttur
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                greining = "".join(greining)
            elif formdeildir[1] == "NH": #nh.
                # greining = orðfl+háttur+mynd(+"--þ" ef þátíð)
                # nh.: [0]: mynd, [1]: háttur, [2]: tíð ef til staðar(mundu, vildu, ...)
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                if len(formdeildir) == 3: #þátíð
                    greining.append("--þ")
                greining = "".join(greining)
            elif formdeildir[1] == "BH": #bh.
                # greining = orðfl+háttur+mynd+persóna+tala+tíð
                # bh.: [0]: mynd, [1]: háttur, [2]: tala/stýfður
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                greining.append("1en") # TODO persóna, tala og tíð koma hvergi fram í BÍN eða Greyni. Default er 1.p.et.nt. = 1en
                greining = "".join(greining)
            elif formdeildir[0] == "OP": # ópersónulegar sagnir
                # fh. og vh.: [0]: "OP" [1]: mynd, [2]: háttur, [3]: tíð, [4]: persóna, [5]: tala
                #greining = orðfl+háttur+mynd+persóna+tala+tíð
                greining.append(BÍN_MAP[formdeildir[2]]) # háttur
                greining.append(BÍN_MAP[formdeildir[1]]) # mynd
                greining.append(BÍN_MAP[formdeildir[4]]) # persóna
                greining.append(BÍN_MAP[formdeildir[5]]) # tala
                greining.append(BÍN_MAP[formdeildir[3]]) # tíð
                greining = "".join(greining)
            else: #fh. og vh. eða skammstafaðar sagnir
                # greining = orðfl+háttur+mynd+persóna+tala+tíð
                # fh. og vh.: [0]: mynd, [1]: háttur, [2]: tíð, [3]: persóna, [4]: tala
                # Ath. óskháttur varpast í vh.
                if word["b"] == "-" and word["t"] == "so": #Undantekningartilvik
                    return "sxxxxx"
                greining.extend(self.hátturmynd(formdeildir)) # háttur+mynd
                greining.append(BÍN_MAP[formdeildir[3]]) # persóna
                greining.append(BÍN_MAP[formdeildir[4]]) # tala
                greining.append(BÍN_MAP[formdeildir[2]]) # tíð
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
            if len(formdeildir) == 1: #vantar stýringu, get tekið út þegar hef samræmt Greynismörk - # TODO útfæra fyrir hvert og eitt núna
                greining.append("x")
            else:
                greining.append(GrToOTB[formdeildir[1]]) #stýring
            greining = "".join(greining)
        elif tegund == "st":
            c = word["x"]
            if c in "sem" or c in "er": # tilvísunartengingar
                greining = "ct"
            else:
                greining = "c"
        elif tegund == "nhm":
            greining = "cn"
        elif tegund == "töl": # TODO hvert er samband þessara töluorða við önnur töluorð?
            greining = "to"
        else:
            #print("Finn ekki greiningu:", tegund, word["k"], word["t"], word["x"])
            #if "b" in word:
                #print(word["b"])
            pass
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
        #tvennd = (tuple(mark_Gr), tuple(mark_OTB)) # TODO setja aftur inn ef útfæri confusion matrix
        #if tvennd in self.M_confmat:
            #self.M_confmat[tvennd] += 1
        #else:
            #self.M_confmat[tvennd] = 1
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

    def sbrGreinarmerki(self, OTB, word):
        mörkun = False
        if "s" in word:
            lemma_Gr = word["s"]
        elif "x" in word:
            lemma_Gr = word["x"]
        else:
            #print("Lemma finnst ekki: {}".format(*word))
            return False, False
        if lemma_Gr and OTB and lemma_Gr == OTB:
            return True
        else:
            return False

    def hátturmynd(self, bín):
        markhluti = []
        markhluti.append(BÍN_MAP[bín[1]])
        markhluti.append(BÍN_MAP[bín[0]])
        return markhluti

    def kyntalafall(self, bín):
        markhluti = []
        markhluti.append(BÍN_MAP[bín[0]])
        markhluti.append(BÍN_MAP[bín[1]])
        return "".join(markhluti)

    def pk(self, word):
        # Greinir persónu eða kyn
        pk = {
            "ég": "1",
            "þú": "2",
            "hann": "k",
            "hún": "v",
            "það": "h" ,
            "þér": "2",
            "vér": "1"
        }
        if "s" in word:
            return "fp" + pk[word["s"]]
        else:
            return "fp" + pk[word["x"]] # Ætti ekki að gerast
  
    def undirflokkun(self, word):
        fl = {
        "sá": "fa",
        "þessi": "fa",
        "hinn": "fa",
        "slíkur": "fb",
        "sjálfur": "fb",
        "samur": "fb",
        "sami": "fb", # ætti að vera samur
        "þvílíkur": "fb",
        "minn": "fe",
        "þinn": "fe",
        "sinn": "fe",
        "vor": "fe",
        "einhver": "fo",
        "sérhver": "fo",
        "nokkur": "fo",
        "allnokkur": "fo",
        "hvorugur": "fo",
        "allur": "fo",
        "mestallur": "fo",
        "flestallur": "fo",
        "sumur": "fo",
        "enginn": "fo",
        "margur": "fo",
        "flestir": "fo", # æti að vera margur
        "einn": "fo",
        "annar": "fo",
        "neinn": "fo",
        "sitthvað": "fo",
        "ýmis": "fo",
        "fáeinir": "fo",
        "báðir": "fo",
        "hver": "fs",
        "hvor": "fs",
        "hvaða": "fs",
        "hvílíkur": "fs"
        }
        if word["s"] in fl:
            return fl[word["s"]]
        else:
            print(word["x"], word["s"])
            return "fx"
    def prenta(self):
        # Prenta fyrst tíðni
        # Svo reikna nákvæmni, heimt, F-mælingu
        #Setningar
        print()
        print("********************** NIÐURSTÖÐUR ************************")
        print("Réttar setningar:", self.réttar_setningar)
        print("Rangar setningar", self.rangar_setningar)
        print("Ógreindar setningar:", self.ógreindar_setningar)
        if self.réttar_setningar == 0:
            SN, SH, SF = 0, 0, 0
        else:
            SN = self.réttar_setningar / (self.réttar_setningar + self.rangar_setningar)
            SH = self.réttar_setningar / (self.réttar_setningar + self.ógreindar_setningar) # TODO rangar hér?
            SF = (2 * SN * SH) / (SN + SH)
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(SN, SH, SF))
        print("")
        #Orð
        print("Rétt orð:", self.rétt_orð)
        print("Röng orð:", self.röng_orð)
        print("Orð vantar:", self.orð_vantar)
        if self.rétt_orð == 0:
            ON, OH, OF = 0, 0, 0
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
        print("***********************************************************")

        print("")
        # Geymi eina breytu fyrir greinarmerki; geri ráð fyrir að ef markið er rétt er lemman það líka.
        print("************* NIÐURSTÖÐUR MEÐ GREINARMERKJUM **************")
        print("Rétt greinarmerki:", self.GR)
        print("Röng greinarmerki:", self.GW)

        # Orð
        print("Rétt orð:", str(self.rétt_orð + self.GR))
        print("Röng orð:", str(self.röng_orð + self.GW))
        print("Orð vantar:", self.orð_vantar)
        if (self.rétt_orð + self.GR) == 0:
            GON, GOH, GOF = 0, 0, 0
        else:
            GON = (self.rétt_orð + self.GR) / (self.rétt_orð + self.GR + self.GW + self.röng_orð)
            GOH = (self.rétt_orð + self.GR) / (self.rétt_orð + self.GR + self.orð_vantar)
            GOF = (2 * GON * GOH) / (GON + GOH)
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(GON, GOH, GOF))
        print("")
        # Lemmur
        print("Réttar lemmur:", str(self.LR + self.GR))
        print("Rangar lemmur:", str(self.LW + self.GW))
        if (self.LR + self.GR) == 0:
            GLN, GLH, GLF = 0, 0, 0
        else:
            GLN = (self.LR + self.GR) / (self.LR + self.GR + self.GW + self.LW) # Nákvæmni lemmna; (réttar/(réttar+rangar))
            GLH = (self.LR + self.GR) / (self.LR + self.GR + self.orð_vantar) # Heimt lemmna; (réttar/(réttar+vantar))
            GLF = (2 * GLN * GLH) / (GLN + GLH) # F-measure lemmna
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(GLN, GLH, GLF))
        print("")
        # Mörk
        print("Rétt mörk:", str(self.MR + self.GR))
        print("Hlutrétt mörk (réttur orðflokkur):", self.MP)
        print("Röng mörk:", str(self.MW + self.GW))
        if self.MR == 0:
            GMN, GMH, GMF = 0, 0, 0
        else:
            GMN = (self.MR + self.MP + self.GR) / (self.MR + self.MP + self.GR + self.GW + self.MW)
            GMH = (self.MR + self.GR) / (self.MR + self.GR + self.orð_vantar)
            GMF = (2 * GMN * GMH) / (GMN + GMH) # F-measure lemmna
        print("Nákvæmni: {:f}\tHeimt: {:f}\t F-mæling: {:f}".format(GMN, GMH, GMF))
        print("***********************************************************")

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
    liðið = lok - byrjun
    print("")
    print("Keyrslan tók {:f} sekúndur, eða {:f} mínútur.".format(liðið, (liðið / 60.0)))
