# coding=utf-8

CASES = {"nf", "þf", "þgf", "ef"}
GENDERS = {"kk", "kvk", "hk"}
NUMBERS = {"et", "ft"}
PERSONS = {"p1", "p2", "p3"}

TENSE = {"þt", "nt"}
DEGREE = {"mst", "esb", "evb"}  # fst

VOICE = {"mm", "gm"}
MOOD = {"fh", "lhþt", "lhnt", "vh", "bh"}

MISC = {"sagnb", "subj", "abbrev", "op", "none"}


DEFAULT_ID_MAP = {
    "P": dict(name="Málsgrein"),
    "S-MAIN": dict(name="Setning", overrides="S", subject_to={"S-MAIN"}),
    "S": dict(name="Setning", subject_to={"S", "S-EXPLAIN", "S-REF", "IP"}),
    "S-COND": dict(name="Skilyrði", overrides="S"),  # Condition
    "S-CONS": dict(name="Afleiðing", overrides="S"),  # Consequence
    "S-REF": dict(
        name="Tilvísunarsetning", overrides="S", subject_to={"S-REF"}
    ),  # Reference
    "S-EXPLAIN": dict(name="Skýring"),  # Explanation
    "S-QUOTE": dict(name="Tilvitnun"),  # Quote at end of sentence
    "S-PREFIX": dict(name="Forskeyti"),  # Prefix in front of sentence
    "S-ADV-TEMP": dict(name="Tíðarsetning"),  # Adverbial temporal phrase
    "S-ADV-PURP": dict(name="Tilgangssetning"),  # Adverbial purpose phrase
    "S-ADV-ACK": dict(name="Viðurkenningarsetning"),  # Adverbial acknowledgement phrase
    "S-ADV-CONS": dict(name="Afleiðingarsetning"),  # Adverbial consequence phrase
    "S-ADV-CAUSE": dict(name="Orsakarsetning"),  # Adverbial causal phrase
    "S-ADV-COND": dict(name="Skilyrðissetning"),  # Adverbial conditional phrase
    "S-THT": dict(name="Skýringarsetning"),  # Complement clause
    "S-QUE": dict(name="Spurnarsetning"),  # Question clause
    "VP-SEQ": dict(name="Sagnliður"),
    "VP": dict(name="Sögn", overrides="VP-SEQ", subject_to={"VP"}),
    "VP-PP": dict(name="Sögn", overrides="PP"),
    "NP": dict(name="Nafnliður", subject_to={"NP-SUBJ", "NP-OBJ", "NP-IOBJ", "NP-PRD"}),
    "NP-POSS": dict(name="Eignarfallsliður", overrides="NP"),
    "NP-DAT": dict(name="Þágufallsliður", overrides="NP"),
    "NP-ADDR": dict(name="Heimilisfang", overrides="NP"),
    "NP-TITLE": dict(name="Titill", overrides="NP"),
    "NP-SUBJ": dict(name="Frumlag", subject_to={"NP-SUBJ"}),
    "NP-OBJ": dict(name="Beint andlag"),
    "NP-IOBJ": dict(name="Óbeint andlag"),
    "NP-PRD": dict(name="Sagnfylling"),
    "ADVP": dict(name="Atviksliður", subject_to={"ADVP"}),
    "ADVP-DATE": dict(name="Tímasetning", overrides="ADVP", subject_to={"ADVP-DATE"}),
    "PP": dict(name="Forsetningarliður", overrides="ADVP"),
    "ADJP": dict(name="Lýsingarliður", subject_to={"ADJP"}),
    "IP": dict(name="Beygingarliður"),  # Inflectional phrase
}
