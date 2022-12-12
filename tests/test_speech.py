"""

    Greynir: Natural language processing for Icelandic

    Copyright (C) 2022 Miðeind ehf.

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


    Tests for speech-synthesis-related code in the Greynir repo.

"""

import os
import sys
import datetime
import logging
from pathlib import Path
from itertools import product

import requests
from speech import text_to_audio_url
from utility import read_api_key

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)


def test_voices_utils():
    """Test utility functions in speech.voices."""
    from speech.norm import strip_markup
    from speech.voices import (
        mimetype_for_audiofmt,
        suffix_for_audiofmt,
        generate_data_uri,
    )

    assert mimetype_for_audiofmt("mp3") == "audio/mpeg"
    assert mimetype_for_audiofmt("blergh") == "application/octet-stream"

    assert suffix_for_audiofmt("mp3") == "mp3"
    assert suffix_for_audiofmt("blergh") == "data"

    assert strip_markup("hello") == "hello"
    assert strip_markup("<dajs dsajl>hello") == "hello"
    assert strip_markup("<a>hello</a>") == "hello"
    assert strip_markup("<prefer:something>hello</else>") == "hello"

    assert (
        generate_data_uri(b"hello") == "data:application/octet-stream;base64,aGVsbG8="
    )
    assert (
        generate_data_uri(b"hello", mime_type="text/plain")
        == "data:text/plain;base64,aGVsbG8="
    )


def test_speech_synthesis():
    """Test basic speech synthesis functionality."""

    _TEXT = "Prufa"
    _MIN_AUDIO_SIZE = 1000

    # Test AWS Polly
    if read_api_key("AWSPollyServerKey.json"):
        url = text_to_audio_url(
            text=_TEXT,
            text_format="text",
            audio_format="mp3",
            voice_id="Dora",
        )
        assert url and url.startswith("http")
        r = requests.get(url)
        assert r.headers.get("Content-Type") == "audio/mpeg", "Expected MP3 audio data"
        assert len(r.content) > _MIN_AUDIO_SIZE, "Expected longer audio data"
    else:
        logging.info("No AWS Polly API key found, skipping test")

    # Test Azure Cognitive Services
    if read_api_key("AzureSpeechServerKey.json"):
        url = text_to_audio_url(
            text=_TEXT,
            text_format="text",
            audio_format="mp3",
            voice_id="Gudrun",
        )
        assert url and url.startswith("file://") and url.endswith(".mp3")
        path_str = url[7:]
        path = Path(path_str)
        assert path.is_file(), "Expected audio file to exist"
        assert path.stat().st_size > _MIN_AUDIO_SIZE, "Expected longer audio data"
        path.unlink()
    else:
        logging.info("No Azure Speech API key found, skipping test")


def test_gssml():
    from speech.norm import gssml

    gv = gssml("5", type="number")
    assert gv == '<greynir type="number">5</greynir>'
    gv = gssml(type="vbreak")
    assert gv == '<greynir type="vbreak" />'
    gv = gssml(type="vbreak", strength="medium")
    assert gv == '<greynir type="vbreak" strength="medium" />'
    gv = gssml("whatever", type="misc", a="1", b=3, c=4.5)
    assert gv == '<greynir type="misc" a="1" b="3" c="4.5">whatever</greynir>'
    try:
        gssml("something", no_type_arg="hello")  # type: ignore
        assert False, "gssml should raise error if no type arg specified"
    except:
        pass


def test_greynirssmlparser():
    from speech import GreynirSSMLParser, DEFAULT_VOICE, SUPPORTED_VOICES
    from speech.norm import gssml, DefaultNormalization

    gp = GreynirSSMLParser(DEFAULT_VOICE)
    n = gp.normalize(f"Ég vel töluna {gssml(244, type='number', gender='kk')}")
    assert "tvö hundruð fjörutíu og fjórir" in n
    n = gp.normalize(
        f"{gssml(type='vbreak')} {gssml(3, type='number', gender='kk', case='þf')}"
    )
    assert "<break />" in n and "þrjá" in n

    example_data = {
        "number": "1",
        "numbers": "1 2 3",
        "float": "1.0",
        "floats": "1.0 2.3",
        "ordinal": "1",
        "ordinals": "1., 3., 4.",
        "phone": "5885522",
        "time": "12:31",
        "date": "2000-01-01",
        "year": "1999",
        "years": "1999, 2000 og 2021",
        "abbrev": "ASÍ",
        "spell": "SÍBS",
        "vbreak": None,
        "email": "t@olvupostur.rugl",
        "paragraph": "lítil efnisgrein",
        "sentence": "lítil setning eða málsgrein?",
    }

    for t, v in DefaultNormalization.__dict__.items():
        if t not in example_data:
            continue
        assert isinstance(
            v, (staticmethod, classmethod)
        ), "not valid normalization method name"
        d = example_data[t]
        if d is None:
            # No data argument to gssml
            r = f"hér er {gssml(type=t)} texti"
            # Make sure gssml added <greynir/> tag
            assert "<greynir" in r and "/>" in r
        else:
            r = f"hér er {gssml(d, type=t)} texti"
            # Make sure gssml added <greynir> tags
            assert "<greynir" in r and "</greynir" in r
        n = gp.normalize(r)
        # Make sure normalization removes all <greynir> tags
        assert "<greynir" not in n and "</greynir" not in n

    # -------------------------
    # Tests for weird text data (shouldn't happen in normal query processing though)
    # Underlying HTMLParser class doesn't deal correctly with </tag a=">">,
    # nothing easy we can do to fix that
    x = """<ehskrytid> bla</s>  <t></t> <other formatting="fhe"> bla</other> fad <daf <fda> fda"""
    n = gp.normalize(x)
    assert n == x
    # We strip spaces from the names of endtags,
    # but otherwise try to keep unrecognized tags unmodified
    x = """<bla attr="fad" f="3"></ bla  >"""
    n = gp.normalize(x)
    assert n == """<bla attr="fad" f="3"></bla>""" and n.count(" ") <= x.count(" ")

    x = """<bla attr="fad" f="3"><greynir type="vbreak" /></bla> <greynir type="number" gender="kvk">4</greynir>"""
    n = gp.normalize(x)
    assert n == """<bla attr="fad" f="3"><break /></bla> fjórar"""

    x = """<bla attr="fad" f="3"><greynir type="vbreak" /> <greynir type="number" gender="kvk">4</greynir>"""
    n = gp.normalize(x)
    assert n == """<bla attr="fad" f="3"><break /> fjórar"""

    x = """<bla attr="fad" f="3"><greynir type="vbreak" /> <&#47;<greynir type="number" gender="kvk">4</greynir>>"""
    n = gp.normalize(x)
    assert n == """<bla attr="fad" f="3"><break /> </fjórar>"""

    # -------------------------
    # Test voice engine specific normalization

    assert "Dora" in SUPPORTED_VOICES
    # Gudrun, the default voice, and Dora don't spell things the same
    gp2 = GreynirSSMLParser("Dora")
    alphabet = "aábcdðeéfghiíjklmnoópqrstuúvwxyýþæöz"
    n1 = gp.normalize(gssml(alphabet, type="spell"))
    n2 = gp2.normalize(gssml(alphabet, type="spell"))
    assert n1 != n2
    n1 = gp.normalize(gssml(alphabet, type="abbrev"))
    n2 = gp2.normalize(gssml(alphabet, type="abbrev"))
    assert n1 != n2


def test_norm_spell_out() -> None:
    from speech.norm import spell_out

    assert spell_out("LÍÚ") == "ell í ú"
    assert spell_out("líú") == "ell í ú"
    assert spell_out("fTb") == "eff té bé"
    assert spell_out("F t B ") == "eff té bé"
    assert spell_out("YnG") == "ufsilon enn gé"
    assert spell_out(" YnG") == "ufsilon enn gé"


def test_norm_numbers() -> None:
    """Test number handling functionality in queries"""

    from speech.norm.num import (
        number_to_neutral,
        number_to_text,
        numbers_to_text,
    )

    assert number_to_neutral(2) == "tvö"
    assert number_to_neutral(1100) == "eitt þúsund og eitt hundrað"
    assert (
        number_to_neutral(-42178249)
        == "mínus fjörutíu og tvær milljónir eitt hundrað sjötíu og átta þúsund tvö hundruð fjörutíu og níu"
    )
    assert number_to_neutral(241000000000) == "tvö hundruð fjörutíu og einn milljarður"
    assert number_to_neutral(100000000) == "eitt hundrað milljónir"
    assert number_to_neutral(1000001000) == "einn milljarður og eitt þúsund"
    assert number_to_neutral(1000000011) == "einn milljarður og ellefu"
    assert number_to_neutral(1001000000) == "einn milljarður og ein milljón"
    assert number_to_neutral(1002000000) == "einn milljarður og tvær milljónir"
    assert number_to_neutral(200000000000) == "tvö hundruð milljarðar"
    assert (
        number_to_text(1000200200)
        == "einn milljarður tvö hundruð þúsund og tvö hundruð"
    )
    assert (
        number_to_neutral(10000000000000000000000000000000000000000000000000000000)
        == "tíu milljónir oktilljóna"
    )
    assert (
        number_to_neutral(1000000000000000000000000000000000000001000000000)
        == "ein oktilljón og einn milljarður"
    )
    assert (
        number_to_neutral(1000000000000000000000000000000000000003000000000)
        == "ein oktilljón og þrír milljarðar"
    )
    assert number_to_neutral(3000400000) == "þrír milljarðar og fjögur hundruð þúsund"
    assert (
        number_to_neutral(2000000000000000000000000000000000100000000000000)
        == "tvær oktilljónir og eitt hundrað billjónir"
    )
    assert number_to_text(320) == "þrjú hundruð og tuttugu"
    assert number_to_text(320000) == "þrjú hundruð og tuttugu þúsund"
    assert (
        number_to_text(3202020202020)
        == "þrjár billjónir tvö hundruð og tveir milljarðar tuttugu milljónir tvö hundruð og tvö þúsund og tuttugu"
    )
    assert (
        number_to_text(320202020)
        == "þrjú hundruð og tuttugu milljónir tvö hundruð og tvö þúsund og tuttugu"
    )

    assert number_to_text(101, gender="kk") == "hundrað og einn"
    assert number_to_text(-102, gender="kvk") == "mínus hundrað og tvær"
    assert (
        number_to_text(-102, gender="kvk", one_hundred=True)
        == "mínus eitt hundrað og tvær"
    )
    assert number_to_text(5, gender="kk") == "fimm"
    assert number_to_text(10001, gender="kvk") == "tíu þúsund og ein"
    assert (
        number_to_text(113305, gender="kk")
        == "eitt hundrað og þrettán þúsund þrjú hundruð og fimm"
    )
    assert number_to_text(400567, gender="hk") == number_to_neutral(400567)
    assert (
        number_to_text(-11220024, gender="kvk")
        == "mínus ellefu milljónir tvö hundruð og tuttugu þúsund tuttugu og fjórar"
    )
    assert (
        number_to_text(19501180)
        == "nítján milljónir fimm hundruð og eitt þúsund eitt hundrað og áttatíu"
    )

    assert numbers_to_text("135 og -16") == "hundrað þrjátíu og fimm og mínus sextán"
    assert numbers_to_text("-55 manns") == "mínus fimmtíu og fimm manns"
    assert numbers_to_text("Baugatangi 1, Reykjavík") == "Baugatangi eitt, Reykjavík"
    assert numbers_to_text("Baugatangi 2, Reykjavík") == "Baugatangi tvö, Reykjavík"
    assert numbers_to_text("Baugatangi 3, Reykjavík") == "Baugatangi þrjú, Reykjavík"
    assert numbers_to_text("Baugatangi 4, Reykjavík") == "Baugatangi fjögur, Reykjavík"
    assert numbers_to_text("Baugatangi 5, Reykjavík") == "Baugatangi fimm, Reykjavík"
    assert numbers_to_text("Baugatangi 10, Reykjavík") == "Baugatangi tíu, Reykjavík"
    assert numbers_to_text("Baugatangi 11, Reykjavík") == "Baugatangi ellefu, Reykjavík"
    assert numbers_to_text("Baugatangi 12, Reykjavík") == "Baugatangi tólf, Reykjavík"
    assert (
        numbers_to_text("Baugatangi 13, Reykjavík") == "Baugatangi þrettán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 14, Reykjavík") == "Baugatangi fjórtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 15, Reykjavík") == "Baugatangi fimmtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 20, Reykjavík") == "Baugatangi tuttugu, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 21, Reykjavík")
        == "Baugatangi tuttugu og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 22, Reykjavík")
        == "Baugatangi tuttugu og tvö, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 23, Reykjavík")
        == "Baugatangi tuttugu og þrjú, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 24, Reykjavík")
        == "Baugatangi tuttugu og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 25, Reykjavík")
        == "Baugatangi tuttugu og fimm, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 100, Reykjavík") == "Baugatangi hundrað, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 101, Reykjavík")
        == "Baugatangi hundrað og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 102, Reykjavík")
        == "Baugatangi hundrað og tvö, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 103, Reykjavík")
        == "Baugatangi hundrað og þrjú, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 104, Reykjavík")
        == "Baugatangi hundrað og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 105, Reykjavík")
        == "Baugatangi hundrað og fimm, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 111, Reykjavík")
        == "Baugatangi hundrað og ellefu, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 112, Reykjavík")
        == "Baugatangi hundrað og tólf, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 113, Reykjavík")
        == "Baugatangi hundrað og þrettán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 114, Reykjavík")
        == "Baugatangi hundrað og fjórtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 115, Reykjavík")
        == "Baugatangi hundrað og fimmtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 121, Reykjavík")
        == "Baugatangi hundrað tuttugu og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 174, Reykjavík")
        == "Baugatangi hundrað sjötíu og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 200, Reykjavík")
        == "Baugatangi tvö hundruð, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 201, Reykjavík")
        == "Baugatangi tvö hundruð og eitt, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 202, Reykjavík")
        == "Baugatangi tvö hundruð og tvö, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 203, Reykjavík")
        == "Baugatangi tvö hundruð og þrjú, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 204, Reykjavík")
        == "Baugatangi tvö hundruð og fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 205, Reykjavík")
        == "Baugatangi tvö hundruð og fimm, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 211, Reykjavík")
        == "Baugatangi tvö hundruð og ellefu, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 212, Reykjavík")
        == "Baugatangi tvö hundruð og tólf, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 213, Reykjavík")
        == "Baugatangi tvö hundruð og þrettán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 214, Reykjavík")
        == "Baugatangi tvö hundruð og fjórtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 215, Reykjavík")
        == "Baugatangi tvö hundruð og fimmtán, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 700, Reykjavík")
        == "Baugatangi sjö hundruð, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 1-4, Reykjavík")
        == "Baugatangi eitt-fjögur, Reykjavík"
    )
    assert (
        numbers_to_text("Baugatangi 1-17, Reykjavík")
        == "Baugatangi eitt-sautján, Reykjavík"
    )


def test_norm_years() -> None:
    """Test number to written year conversion."""

    from speech.norm.num import year_to_text, years_to_text

    assert year_to_text(1999) == "nítján hundruð níutíu og níu"
    assert year_to_text(2004) == "tvö þúsund og fjögur"
    assert year_to_text(-501) == "fimm hundruð og eitt fyrir Krist"
    assert year_to_text(1001, after_christ=True) == "eitt þúsund og eitt eftir Krist"
    assert year_to_text(57, after_christ=True) == "fimmtíu og sjö eftir Krist"
    assert year_to_text(2401) == "tvö þúsund fjögur hundruð og eitt"

    assert (
        years_to_text("Ég fæddist 1994") == "Ég fæddist nítján hundruð níutíu og fjögur"
    )
    assert (
        years_to_text("Árið 1461 var borgin Sarajevo stofnuð")
        == "Árið fjórtán hundruð sextíu og eitt var borgin Sarajevo stofnuð"
    )
    assert (
        years_to_text("17. júlí 1210 lést Sverker II")
        == "17. júlí tólf hundruð og tíu lést Sverker II"
    )
    assert (
        years_to_text("2021, 2007 og 1999")
        == "tvö þúsund tuttugu og eitt, tvö þúsund og sjö og nítján hundruð níutíu og níu"
    )


def test_norm_ordinals() -> None:
    """Test number to written ordinal conversion."""

    from speech.norm.num import number_to_ordinal, numbers_to_ordinal

    assert number_to_ordinal(0) == "núllti"
    assert number_to_ordinal(22, case="þgf", gender="kvk") == "tuttugustu og annarri"
    assert number_to_ordinal(302, gender="kvk") == "þrjú hundraðasta og önnur"
    assert number_to_ordinal(302, case="þgf", gender="hk") == "þrjú hundraðasta og öðru"
    assert (
        number_to_ordinal(-302, case="þgf", gender="hk")
        == "mínus þrjú hundraðasta og öðru"
    )
    assert (
        number_to_ordinal(10202, case="þgf", gender="hk", number="ft")
        == "tíu þúsund tvö hundruðustu og öðrum"
    )
    assert (
        number_to_ordinal(1000000, case="þf", gender="kvk", number="et")
        == "milljónustu"
    )
    assert (
        number_to_ordinal(1000000002, case="þf", gender="kvk", number="et")
        == "milljörðustu og aðra"
    )

    assert (
        numbers_to_ordinal("Ég lenti í 41. sæti.", case="þgf")
        == "Ég lenti í fertugasta og fyrsta sæti."
    )
    assert (
        numbers_to_ordinal("Ég lenti í -41. sæti.", case="þgf")
        == "Ég lenti í mínus fertugasta og fyrsta sæti."
    )
    assert numbers_to_ordinal("-4. sæti.", case="þgf") == "mínus fjórða sæti."
    assert (
        numbers_to_ordinal("2. í röðinni var hæstur.") == "annar í röðinni var hæstur."
    )
    assert (
        numbers_to_ordinal("1. konan lenti í 2. sæti.", regex=r"1\.", gender="kvk")
        == "fyrsta konan lenti í 2. sæti."
    )
    assert (
        numbers_to_ordinal("fyrsta konan lenti í 2. sæti.", gender="hk", case="þgf")
        == "fyrsta konan lenti í öðru sæti."
    )
    assert (
        numbers_to_ordinal("Ég var 10201. í röðinni.")
        == "Ég var tíu þúsund tvö hundraðasti og fyrsti í röðinni."
    )
    assert (
        numbers_to_ordinal(
            "Björn sækist eftir 1. - 4. sæti í Norðvesturkjördæmi", case="þgf"
        ).replace("-", "til")
        == "Björn sækist eftir fyrsta til fjórða sæti í Norðvesturkjördæmi"
    )
    assert (
        numbers_to_ordinal(
            "Björn sækist eftir 1.-4. sæti í Norðvesturkjördæmi", case="þgf"
        ).replace("-", " til ")
        == "Björn sækist eftir fyrsta til fjórða sæti í Norðvesturkjördæmi"
    )
    assert (
        numbers_to_ordinal("1.-4. sæti í Norðvesturkjördæmi", case="þgf").replace(
            "-", " til "
        )
        == "fyrsta til fjórða sæti í Norðvesturkjördæmi"
    )


def test_norm_floats() -> None:
    """Test float to written text conversion."""

    from speech.norm.num import float_to_text, floats_to_text

    assert float_to_text(-0.12) == "mínus núll komma tólf"
    assert float_to_text(-0.1012) == "mínus núll komma eitt núll eitt tvö"
    assert (
        float_to_text(-0.1012, gender="kk") == "mínus núll komma einn núll einn tveir"
    )
    assert float_to_text(-21.12, gender="kk") == "mínus tuttugu og einn komma tólf"
    assert (
        float_to_text(-21.123, gender="kk")
        == "mínus tuttugu og einn komma einn tveir þrír"
    )
    assert float_to_text(1.03, gender="kvk") == "ein komma núll þrjár"
    assert float_to_text(2.0, gender="kvk", case="þgf") == "tveimur"
    assert (
        float_to_text(2.0, gender="kvk", case="þgf", comma_null=True)
        == "tveimur komma núll"
    )

    assert (
        floats_to_text("2,13 millilítrar af vökva.", gender="kk")
        == "tveir komma þrettán millilítrar af vökva."
    )
    assert floats_to_text("0,04 prósent.") == "núll komma núll fjögur prósent."
    assert floats_to_text("-0,04 prósent.") == "mínus núll komma núll fjögur prósent."
    assert (
        floats_to_text("101,0021 prósent.")
        == "hundrað og eitt komma núll núll tuttugu og eitt prósent."
    )
    assert (
        floats_to_text("10.100,21 prósent.")
        == "tíu þúsund og eitt hundrað komma tuttugu og eitt prósent."
    )
    assert (
        floats_to_text("Um -10.100,21 prósent.")
        == "Um mínus tíu þúsund og eitt hundrað komma tuttugu og eitt prósent."
    )
    assert (
        floats_to_text("-10.100,21 prósent.")
        == "mínus tíu þúsund og eitt hundrað komma tuttugu og eitt prósent."
    )
    assert floats_to_text("2.000.000,00.", comma_null=False) == "tvær milljónir."


def test_norm_digits() -> None:
    """Test digit string to written text conversion."""

    from speech.norm.num import digits_to_text

    assert digits_to_text("5885522") == "fimm átta átta fimm fimm tveir tveir"
    assert digits_to_text("112") == "einn einn tveir"
    assert digits_to_text("123-0679") == "einn tveir þrír-núll sex sjö níu"
    assert (
        digits_to_text("Síminn minn er 12342")
        == "Síminn minn er einn tveir þrír fjórir tveir"
    )
    assert digits_to_text("581 2345") == "fimm átta einn tveir þrír fjórir fimm"
    assert (
        digits_to_text("5812345, það er síminn hjá þeim.")
        == "fimm átta einn tveir þrír fjórir fimm, það er síminn hjá þeim."
    )
    assert (
        digits_to_text("010270-2039")
        == "núll einn núll tveir sjö núll-tveir núll þrír níu"
    )
    assert (
        digits_to_text("192 0-1-127", regex=r"\d\d\d")
        == "einn níu tveir 0-1-einn tveir sjö"
    )
    assert (
        digits_to_text("Hringdu í 1-800-BULL", regex=r"\d+-\d+")
        == "Hringdu í einn átta núll núll-BULL"
    )


def test_norm_time_handler() -> None:
    from speech.norm import DefaultNormalization

    assert DefaultNormalization.time(f"00:00") == "tólf á miðnætti"
    assert DefaultNormalization.time(f"12:00") == "tólf á hádegi"
    midnight = datetime.time(0, 0)
    six_am = datetime.time(6, 0)
    for h, m in product(range(24), range(60)):
        t = datetime.time(h, m)
        n1 = DefaultNormalization.time(f"{t.hour}:{t.minute}")
        assert n1.replace(" ", "").isalpha()
        n2 = DefaultNormalization.time(t.strftime("%H:%M"))
        assert n2.replace(" ", "").isalpha()
        assert n1 == n2
        if midnight < t < six_am:
            assert "um nótt" in n1


def test_norm_date_handler() -> None:
    from speech.norm import DefaultNormalization
    from settings import changedlocale

    with changedlocale(category="LC_TIME"):
        for d, m, y, case in product(
            range(1, 32),
            range(1, 13),
            (1, 100, 1800, 1850, 1900, 1939, 2022),
            ("nf", "þf", "þgf", "ef"),
        ):
            try:
                date = datetime.date(y, m, d)
            except:
                continue
            n1 = DefaultNormalization.date(date.isoformat(), case=case)
            assert n1 == DefaultNormalization.date(f"{y}-{m}-{d}", case=case)
            n2 = DefaultNormalization.date(f"{d}/{m}/{y}", case=case)
            assert n2 == DefaultNormalization.date(date.strftime("%d/%m/%Y"), case=case)
            n3 = DefaultNormalization.date(date.strftime("%d. %B %Y"), case=case)
            n4 = DefaultNormalization.date(date.strftime("%d. %b %Y"), case=case)
            assert n1 == n2 == n3 == n4


def test_norm_abbrev_handler() -> None:
    from speech.norm import DefaultNormalization

    for a in ("ASÍ", "LSH", "AÁBDÐEÉFIÍJKLMNOÓPQRSTUÚVWXYÝZÆÖ"):
        n1 = DefaultNormalization.abbrev(a.upper())
        n2 = DefaultNormalization.abbrev(a.lower())
        n3 = DefaultNormalization.abbrev(a.upper())
        n4 = DefaultNormalization.spell(a.lower())
        assert n1 == n2 == n3 == n4
        assert n1.islower()


def test_norm_email_handler() -> None:
    from speech.norm import DefaultNormalization

    for e in (
        "jon.jonsson@mideind.is",
        "gunnar.brjann@youtube.gov.uk",
        "tolvupostur@gmail.com",
    ):
        n = DefaultNormalization.email(e)
        assert "@" not in n and " hjá " in n
        assert "." not in n and " punktur " in n


def test_norm_vbreak_handler() -> None:
    from speech.norm import (
        DefaultNormalization,
        _STRENGTHS,  # type: ignore
    )

    assert DefaultNormalization.vbreak() == "<break />"
    for t in ("0ms", "50ms", "1s", "1.7s"):
        n = DefaultNormalization.vbreak(time=t)
        assert n == f'<break time="{t}" />'
    for s in _STRENGTHS:
        n = DefaultNormalization.vbreak(strength=s)
        assert n == f'<break strength="{s}" />'
