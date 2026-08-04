"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2026 Miðeind ehf.

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


    Tests for the HTML-to-text extraction in fetcher.py, in particular
    the invariant that [[...]] paragraph markers in the extracted text
    are always balanced, non-nested and flat. The tokenizer only
    recognizes '[[' at the start of a text chunk, ']]' at its end, and
    exact ']][[' splits; markers in any other position are tokenized
    as literal bracket punctuation and leak into stored parses and the
    displayed article text on greynir.is.

"""

import os
import re
import sys

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)

from bs4 import BeautifulSoup

from fetcher import Fetcher
from tokenizer import TOK, tokenize

# Matches a well-formed extraction result: a flat sequence of
# [[...]] paragraphs whose content contains no marker-like bracket runs
_WELL_FORMED = re.compile(r"(?:\[\[(?:(?!\[\[|\]\])[^\n])*\]\])*\Z")


def extract(html: str) -> str:
    """Run HTML through the fetcher's text extraction"""
    tlist = Fetcher.TextList()
    Fetcher.extract_text(BeautifulSoup(html, "html.parser"), tlist)
    return tlist.result()


def leaked_brackets(text: str) -> int:
    """Tokenize an extraction result and count bracket punctuation
    tokens, i.e. paragraph markers that the tokenizer did not
    recognize as such"""
    return sum(
        1
        for t in tokenize(text)
        if t.kind == TOK.PUNCTUATION and t.txt in ("[", "]", "[[", "]]")
    )


def test_simple_paragraphs() -> None:
    assert extract("<p>Fyrsta málsgrein.</p><p>Önnur málsgrein.</p>") == (
        "[[Fyrsta málsgrein.]][[Önnur málsgrein.]]"
    )
    # Nested block tags produce flat, not nested, markers
    assert extract("<div><p>Fyrsta.</p><p>Önnur.</p></div>") == (
        "[[Fyrsta.]][[Önnur.]]"
    )
    # Empty and whitespace-only blocks produce no markers
    assert extract("<p></p><div> </div><p>Texti.</p>") == "[[Texti.]]"
    assert extract("") == ""


def test_inline_text_between_blocks() -> None:
    """Inline text that is a sibling of block elements must become its
    own paragraph; previously it orphaned the neighboring markers,
    which then leaked as bracket punctuation"""
    assert extract("<div>Inngangur hér. <p>Málsgrein.</p> Lokaorð hér.</div>") == (
        "[[Inngangur hér.]][[Málsgrein.]][[Lokaorð hér.]]"
    )
    # Bare text fragment between two paragraphs (as seen in ruv.is
    # text_block fragments)
    assert extract("<p>Fyrsta.</p>Millitexti án umbúða.<p>Önnur.</p>") == (
        "[[Fyrsta.]][[Millitexti án umbúða.]][[Önnur.]]"
    )
    # Inline text followed by a doubly nested block (ruv.is image
    # caption case: text ran straight into '[[[[')
    assert extract(
        "Hann sagði margt.<figure><figcaption>Mynd af manni.</figcaption></figure>"
    ) == "[[Hann sagði margt.]][[Mynd af manni.]]"
    # Block followed by inline attribution text (visir.is embedded
    # tweet case: ']]' ran straight into the attribution)
    assert extract(
        "<blockquote><p>Tweet content here.</p></blockquote>- Reuters (@Reuters)"
    ) == "[[Tweet content here.]][[- Reuters (@Reuters)]]"


def test_break_tags() -> None:
    # <br> splits a paragraph
    assert extract("<p>Fyrri hluti.<br>Seinni hluti.</p>") == (
        "[[Fyrri hluti.]][[Seinni hluti.]]"
    )
    # Leading, trailing and consecutive <br> produce no stray markers
    assert extract("<br><p>Texti.</p><br>") == "[[Texti.]]"
    assert extract("<p>Fyrri.<br><br><hr>Seinni.</p>") == "[[Fyrri.]][[Seinni.]]"


def test_inline_elements() -> None:
    # <span> boundaries insert whitespace so words don't run together
    assert extract("<p>fyrir<span>miðjan</span>eftir</p>") == "[[fyrir miðjan eftir]]"
    # <img> is treated as whitespace
    assert extract("<p>fyrir<img src='x.jpg'>eftir</p>") == "[[fyrir eftir]]"
    # Non-block inline tags don't split paragraphs
    assert extract("<p>Hann <b>sagði</b> margt.</p>") == "[[Hann sagði margt.]]"


def test_literal_brackets_in_content() -> None:
    # Single brackets in content are preserved
    assert extract("<p>Sjá [mynd] hér.</p>") == "[[Sjá [mynd] hér.]]"
    # Double (or longer) bracket runs in content are collapsed so they
    # can't masquerade as paragraph markers
    assert (
        extract("<p>Sjá [[skrýtna]] hornklofa.</p>")
        == "[[Sjá [skrýtna] hornklofa.]]"
    )
    # Content brackets at paragraph edges are padded away from the markers
    assert extract("<p>[[[þrefalt]]]</p>") == "[[ [þrefalt] ]]"
    assert extract("<p>[hornklofi fremst</p>") == "[[ [hornklofi fremst]]"
    assert extract("<p>hornklofi aftast]</p>") == "[[hornklofi aftast] ]]"
    # In all cases the markers must round-trip through the tokenizer,
    # leaving exactly the single content brackets behind
    for html, n_brackets in [
        ("<p>Sjá [mynd] hér.</p>", 2),
        ("<p>Sjá [[skrýtna]] hornklofa.</p>", 2),
        ("<p>[[[þrefalt]]]</p>", 2),
        ("<p>[hornklofi fremst</p>", 1),
        ("<p>hornklofi aftast]</p>", 1),
        ("<p>a[</p><p>]b</p>", 2),
    ]:
        text = extract(html)
        assert _WELL_FORMED.match(text), f"Malformed markers for {html!r}: {text!r}"
        toks = list(tokenize(text))
        assert sum(1 for t in toks if t.kind == TOK.P_BEGIN) == sum(
            1 for t in toks if t.kind == TOK.P_END
        )
        assert leaked_brackets(text) == n_brackets, f"{html!r}: {text!r}"


def test_marker_invariant() -> None:
    """The extraction result must always be a flat sequence of balanced
    [[...]] paragraphs, and tokenizing it must never leak bracket
    punctuation, regardless of how gnarly the input HTML is"""
    cases = [
        "<p>Venjulegt.</p>",
        "<div>Texti <p>innri</p> meira <p>enn innri</p> loka</div>",
        "<div><div><div>djúpt</div></div></div>",
        "texti á rótarstigi",
        "<br>",
        "<br>texti eftir br",
        "<div><br></div>",
        "<table><tr><td>reitur eitt</td><td>reitur tvö</td></tr></table>",
        "<ul><li>fyrsti</li><li>annar <p>með málsgrein</p> eftirmáli</li></ul>",
        "fyrir<figure><figcaption>myndatexti</figcaption></figure>eftir",
        "<blockquote>tíst</blockquote>- Höfundur (@notandi) 4. ágúst 2026",
        "<p>fyrri</p>millitexti<p>seinni</p>",
        "<div>a<p>b</p>c<p>d</p>e</div>",
        "<span>bara span</span>",
        "<p><span>span í p</span></p>",
        "<h1>Fyrirsögn</h1>texti<h2>Millifyrirsögn</h2>meiri texti",
    ]
    for html in cases:
        text = extract(html)
        assert _WELL_FORMED.match(text), f"Malformed markers for {html!r}: {text!r}"
        assert leaked_brackets(text) == 0, f"Leaked brackets for {html!r}: {text!r}"


def test_paragraph_round_trip() -> None:
    """Paragraph markers produced by the fetcher must be fully consumed
    by the tokenizer as P_BEGIN/P_END tokens"""
    text = extract("<div>Inngangur.<p>Fyrsta málsgrein er hér.</p>Lokaorð.</div>")
    toks = list(tokenize(text))
    n_begin = sum(1 for t in toks if t.kind == TOK.P_BEGIN)
    n_end = sum(1 for t in toks if t.kind == TOK.P_END)
    assert n_begin == 3
    assert n_end == 3
    # No token text should contain a square bracket
    assert not any("[" in t.txt or "]" in t.txt for t in toks if t.txt)
