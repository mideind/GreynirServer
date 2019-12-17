#!/usr/bin/env python3
"""
    Reynir: Natural language processing for Icelandic

    Copyright (C) 2019 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.
"""

from __future__ import print_function
from pprint import pprint

from nn.nnclient import TranslateClient, ParsingClient
from nn.nntree import (
    Node,
    parse_tree_with_text,
    tokenize_and_merge_possible_mw_tokens,
    flat_matching_nonterminal,
    flat_is_terminal,
    flat_is_nonterminal,
    parse_tree
)


def send_test_parse():
    sample_phrase = (
        "Eftirfarandi skilaboð voru smíðuð í Nnclient og þau skulu verða þáttuð."
    )
    print("Sending test translate phrase to server:", sample_phrase)
    res = ParsingClient.request_sentence(sample_phrase)
    print("Received response:")
    print(res)


def test_translate_sentence():
    sample_phrase = "Hæ."
    print("sample_phrase:", sample_phrase)
    res = TranslateClient.request_sentence(sample_phrase)
    print("processed_output:", res)
    print()


def test_translate_text():
    sample_phrase = "Hæ.\nHvernig?"
    print('sample_phrase: """', sample_phrase, '"""', sep="")
    print()
    res = TranslateClient.request_text(sample_phrase)
    print("processed_output:", res)
    print()


def test_reynir_dict_format():
    from reynir import Reynir

    parser = Reynir()
    text = "hún fer"
    sent = parser.parse_single(text)

    print("text:", text)
    print()

    print("reynir flat tree:")
    print(sent.tree.flat)
    print()

    res = sent.tree._view(1)
    print("reynir tree as view:")
    print(res)
    print()

    print("reynir tree as dict:")
    pprint(sent.tree._head)
    print()


def test_reynir_terminal():
    text_tok = "hún"
    from reynir import Reynir
    from reynir.matcher import SimpleTree

    parser = Reynir()
    sent = parser.parse_single(text_tok)

    print("Parsing text:", text_tok)
    print()

    print("flat tree:")
    print(sent.tree.flat)

    print("tree view:")
    print(sent.tree._view(1))

    print("tree._head:")
    dtree = sent.tree._head
    pprint(dtree)

    print("tree._sents:")
    sents_attr = sent.tree._sents
    pprint(sents_attr)

    print("reparse _sents")
    stree = SimpleTree([sents_attr])
    print(stree)
    pprint(stree._head)


def test_nntree_terminal():
    text_tok = "hún"
    parse_tok = "pfn_kvk_et_nf"
    from reynir.matcher import SimpleTree

    terminal = Node(parse_tok, data=text_tok, is_terminal=True)
    dtree = terminal.to_dict()

    print("parsing flat tree to simple tree:")
    print("flat tree:", parse_tok)
    print("with text", text_tok)
    print()

    print("parsed flat tree as dict:")
    print(dtree)

    print("parsed flat tree as SimpleTree")
    stree = SimpleTree([[dtree]])
    print(stree)
    print()


def test_parse_with_text():
    from reynir.matcher import SimpleTree

    text = "hún fer"
    nnparser_toks = "P S-MAIN IP NP-SUBJ pfn_et_kvk_nf_p3 /NP-SUBJ VP so_0_et_fh_gm_nt_p3 /VP /IP /S-MAIN /P"
    parse_toks = nnparser_toks
    nntree, presult = parse_tree_with_text(parse_toks, text)

    print("parsing flat tree to simple tree:")
    print("flat tree:", parse_toks)
    print("with text", text)
    print()

    print("parsed flat tree as nntree dict:")
    dtree = nntree.to_dict()
    pprint(dtree)
    print()

    print("parsed flat tree as SimpleTree view:")
    print(SimpleTree([[dtree]])._view(1))


def test_nntree_to_simple_tree():
    from reynir.matcher import SimpleTree

    text = "hún fer"
    # nnparser_toks
    parse_toks = "P S-MAIN IP NP-SUBJ pfn_et_kvk_nf_p3 /NP-SUBJ VP so_0_et_fh_gm_nt_p3 /VP /IP /S-MAIN /P"
    nntree, presult = parse_tree_with_text(parse_toks, text)

    print("parsing flat tree to simple tree:")
    print("flat tree:", parse_toks)
    print("with text", text)
    print()

    print("nntree:")
    nntree.pprint()
    print()

    print("nntree to SimpleTree:")
    print(nntree.to_simple_tree()._view(1))
    print()


def test_parse():
    sample = (
        "P S-MAIN IP NP-SUBJ pfn_kvk_et_nf /NP-SUBJ VP so_0_et_p3 /VP /IP /S-MAIN /P"
    )
    res = parse_tree(sample)
    print(res)


def test_merge_person():
    text = "Ingibjörg Sólrún Gísladóttir mun a.m.k. hitta hópinn á morgun"
    flat_tree = "P S-MAIN IP NP-SUBJ person_kvk_nf person_kvk_nf person_kvk_nf /NP-SUBJ VP-SEQ VP so_et_fh_gm_nt_p3 ADVP ao /ADVP so_1_þf_gm_nh NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP ADVP ADVP-DATE-REL ao ao /ADVP-DATE-REL /ADVP /VP-SEQ /IP /S-MAIN /P"
    text_toks, parse_toks = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
    assert len(text_toks) == 6

    # change parse token in for person token
    text = "Ingibjörg Sólrún Gísladóttir mun a.m.k. hitta hópinn á morgun"
    flat_tree = "P S-MAIN IP NP-SUBJ person_kvk_nf no_kvk_nf person_kvk_nf /NP-SUBJ VP-SEQ VP so_et_fh_gm_nt_p3 ADVP ao /ADVP so_1_þf_gm_nh NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP ADVP ADVP-DATE-REL ao ao /ADVP-DATE-REL /ADVP /VP-SEQ /IP /S-MAIN /P"
    text_toks, parse_toks = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
    assert len(text_toks) == 8

    # change parse token for ao
    text = "Ingibjörg Sólrún Gísladóttir mun a.m.k. hitta hópinn á morgun"
    flat_tree = "P S-MAIN IP NP-SUBJ person_kvk_nf no_kvk_nf person_kvk_nf /NP-SUBJ VP-SEQ VP so_et_fh_gm_nt_p3 ADVP ao /ADVP so_1_þf_gm_nh NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP ADVP ADVP-DATE-REL fs ao /ADVP-DATE-REL /ADVP /VP-SEQ /IP /S-MAIN /P"
    text_toks, parse_toks = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
    assert len(text_toks) == 54

    text = "Þetta er í fimmta sinn sem málið er lagt fram en upphaflega flutti málið núverandi hæstv. dómsmálaráðherra, Áslaug Arna Sigurbjörnsdóttir, og hefur hún verið fyrsti flutningsmaður að málinu hingað til, en við sem flytjum það núna eru Vilhjálmur Árnason, Óli Björn Kárason, Páll Magnússon, Njáll Trausti Friðbertsson, Bryndís Haraldsdóttir, Brynjar Níelsson, Ásmundur Friðriksson og Jón Gunnarsson."
    flat_tree = "S0 S-MAIN IP NP-SUBJ fn_et_hk_nf /NP-SUBJ VP VP so_1_nf_et_fh_gm_nt_p3 /VP PP P fs_þf /P NP lo_et_hk_þf no_et_hk_þf CP-REL C stt /C IP S-MAIN VP NP-PRD no_et_gr_hk_nf /NP-PRD VP so_1_nf_et_fh_gm_nt_p3 /VP NP-PRD VP so_et_hk_lhþt_nf_sb /VP /NP-PRD /VP ADVP ao /ADVP /S-MAIN /IP C st /C IP S-MAIN ADVP ao /ADVP VP VP so_1_þf_et_fh_gm_p3_þt /VP NP-OBJ no_et_gr_hk_þf NP-POSS lo_ef_et_kk_sb lo_ef_et_kk no_ef_et_kk p S-MAIN IP NP-SUBJ person_kvk_nf person_kvk_nf person_kvk_nf p S-MAIN IP ADVP ao /ADVP VP VP VP-AUX so_et_fh_gm_nt_p3 /VP-AUX NP-SUBJ pfn_et_kvk_nf_p3 /NP-SUBJ VP VP so_1_nf_gm_sagnb /VP NP-PRD lo_et_kk_nf_vb no_et_kk_nf /NP-PRD /VP /VP PP P fs_þgf /P NP no_et_gr_hk_þgf /NP /PP ADVP ao ao /ADVP /VP /IP /S-MAIN p C st /C pfn_ft_nf_p1 CP-REL C stt /C IP S-MAIN VP VP so_1_þf_fh_ft_gm_nt_p1 /VP NP-OBJ pfn_et_hk_p3_þf /NP-OBJ /VP ADVP ao /ADVP /S-MAIN /IP /CP-REL /NP-SUBJ VP VP so_1_nf_fh_ft_gm_nt_p3 /VP NP-PRD person_kk_nf person_kk_nf /NP-PRD /VP /IP /S-MAIN p /NP-POSS /NP-OBJ /VP /S-MAIN /IP /CP-REL /NP /PP NP-PRD person_kk_nf person_kk_nf person_kk_nf p person_kk_nf person_kk_nf p person_kk_nf person_kk_nf person_kk_nf p person_kvk_nf person_kvk_nf p person_kk_nf person_kk_nf p person_kk_nf person_kk_nf C st /C person_kk_nf person_kk_nf /NP-PRD /VP /IP /S-MAIN p /S0"
    text_toks, parse_toks = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
    assert len(text_toks) == 9


def test_flat_fns():
    nonterms = ["P", "S0", "NP-SUBJ"]
    for nt in nonterms:
        assert flat_is_nonterminal(nt), "{} should be nonterminal".format(nt)
    match = ["/NP-SUBJ", "NP-SUBJ"]
    assert flat_matching_nonterminal(match[0]) == match[1], "{} should match {}".format(
        *match
    )
    assert flat_matching_nonterminal(match[1]) == match[0], "{} should match {}".format(
        *match
    )
    terms = ["so_1_nf_et_fh_gm_nt_p3", "lo_et_hk_þf", "tö"]
    for term in terms:
        assert flat_is_terminal(term), "{} should be terminal".format(term)
