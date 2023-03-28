# type: ignore
"""
    Greynir: Natural language processing for Icelandic

    Copyright (C) 2023 Miðeind ehf.

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

from nn.nntree import (
    tokenize_and_merge_possible_mw_tokens,  # type: ignore
    flat_matching_nonterminal,  # type: ignore
    flat_is_terminal,  # type: ignore
    flat_is_nonterminal,  # type: ignore
)


def test_merge_person():
    text = "Ingibjörg Sólrún Gísladóttir mun a.m.k. hitta hópinn á morgun"
    flat_tree = "P S-MAIN IP NP-SUBJ person_kvk_nf person_kvk_nf person_kvk_nf /NP-SUBJ VP-SEQ VP so_et_fh_gm_nt_p3 ADVP ao /ADVP so_1_þf_gm_nh NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP ADVP ADVP-DATE-REL ao ao /ADVP-DATE-REL /ADVP /VP-SEQ /IP /S-MAIN /P"
    text_toks, _ = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
    assert len(text_toks) == 6


def test_merge_ao():
    text = "Ingibjörg Sólrún Gísladóttir mun a.m.k. hitta hópinn á morgun"
    flat_tree = "P S-MAIN IP NP-SUBJ person_kvk_nf no_kvk_nf person_kvk_nf /NP-SUBJ VP-SEQ VP so_et_fh_gm_nt_p3 ADVP ao /ADVP so_1_þf_gm_nh NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP ADVP ADVP-DATE-REL ao ao /ADVP-DATE-REL /ADVP /VP-SEQ /IP /S-MAIN /P"
    text_toks, _ = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
    assert len(text_toks) == 8


def test_no_merge():
    text = "Ingibjörg Sólrún Gísladóttir mun a.m.k. hitta hópinn á morgun"
    flat_tree = "P S-MAIN IP NP-SUBJ person_kvk_nf no_kvk_nf person_kvk_nf /NP-SUBJ VP-SEQ VP so_et_fh_gm_nt_p3 ADVP ao /ADVP so_1_þf_gm_nh NP-OBJ no_et_gr_kk_þf /NP-OBJ /VP ADVP ADVP-DATE-REL fs ao /ADVP-DATE-REL /ADVP /VP-SEQ /IP /S-MAIN /P"
    text_toks, _ = tokenize_and_merge_possible_mw_tokens(text, flat_tree)
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
