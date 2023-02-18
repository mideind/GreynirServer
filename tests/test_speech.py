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


    Tests for speech-synthesis-related code in the Greynir repo.

"""
from typing import Callable

import os
import re
import sys
import datetime
import logging
from pathlib import Path
from itertools import product

import requests
from speech import text_to_audio_url
from speech.trans import DefaultTranscriber as DT
from utility import read_api_key

# Shenanigans to enable Pytest to discover modules in the
# main workspace directory (the parent of /tests)
basepath, _ = os.path.split(os.path.realpath(__file__))
mainpath = os.path.join(basepath, "..")
if mainpath not in sys.path:
    sys.path.insert(0, mainpath)


def test_voices_utils():
    """Test utility functions in speech.voices."""
    from speech.trans import strip_markup
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
        r = requests.get(url, timeout=10)
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
    from speech.trans import gssml

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
    from speech.trans import gssml

    gp = GreynirSSMLParser(DEFAULT_VOICE)
    n = gp.transcribe(f"Ég vel töluna {gssml(244, type='number', gender='kk')}")
    assert "tvö hundruð fjörutíu og fjórir" in n
    n = gp.transcribe(
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
        "abbrev": "t.d.",
        "spell": "SÍBS",
        "vbreak": None,
        "email": "t@olvupostur.rugl",
        "paragraph": "lítil efnisgrein",
        "sentence": "lítil setning eða málsgrein?",
    }

    for t, v in DT.__dict__.items():
        if t not in example_data:
            continue
        assert isinstance(
            v, (staticmethod, classmethod)
        ), "not valid transcription method name"
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
        n = gp.transcribe(r)
        # Make sure transcription removes all <greynir> tags
        assert "<greynir" not in n and "</greynir" not in n

    # -------------------------
    # Tests for weird text data (shouldn't happen in normal query processing though)
    # Underlying HTMLParser class doesn't deal correctly with </tag a=">">,
    # nothing easy we can do to fix that
    x = """<ehskrytid> bla</s>  <t></t> <other formatting="fhe"> bla</other> fad <daf <fda> fda"""
    n = gp.transcribe(x)
    assert "&" not in n and "<" not in n and ">" not in n
    assert len(n) > 0
    # We strip spaces from the names of endtags,
    # but otherwise try to keep unrecognized tags unmodified
    x = """<bla attr="fad" f="3"></ bla  >"""
    n = gp.transcribe(x)
    assert "&" not in n and "<" not in n and ">" not in n
    assert n == ""

    x = """<bla attr="fad" f="3"><greynir type="vbreak" /></bla> <greynir type="number" gender="kvk">4</greynir>"""
    n = gp.transcribe(x)
    assert "&" not in n and n.count("<") == 1 and n.count(">") == 1
    assert n == """<break /> fjórar"""

    x = """<bla attr="fad" f="3"><greynir type="vbreak" /> <greynir type="number" gender="kvk">4</greynir>"""
    n = gp.transcribe(x)
    assert "&" not in n and n.count("<") == 1 and n.count(">") == 1
    assert n == """<break /> fjórar"""

    x = """<bla attr="fad" f="3"><greynir type="vbreak" /> <&#47;<greynir type="number" gender="kvk">4</greynir>>"""
    n = gp.transcribe(x)
    assert "&" not in n and n.count("<") == 1 and n.count(">") == 1

    # -------------------------
    # Test voice engine specific transcription

    assert "Dora" in SUPPORTED_VOICES
    # Gudrun, the default voice, and Dora don't spell things the same
    gp2 = GreynirSSMLParser("Dora")
    alphabet = "aábcdðeéfghiíjklmnoópqrstuúvwxyýþæöz"
    n1 = gp.transcribe(gssml(alphabet, type="spell"))
    n2 = gp2.transcribe(gssml(alphabet, type="spell"))
    assert n1 != n2


def test_number_transcription() -> None:
    """Test number handling functionality in queries"""

    from speech.trans.num import (
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


def test_year_transcription() -> None:
    """Test number to written year conversion."""

    from speech.trans.num import year_to_text, years_to_text

    assert year_to_text(1999) == "nítján hundruð níutíu og níu"
    assert year_to_text(2004) == "tvö þúsund og fjögur"
    assert year_to_text(-501) == "fimm hundruð og eitt fyrir Krist"
    assert year_to_text(1001) == "eitt þúsund og eitt"
    assert year_to_text(57) == "fimmtíu og sjö"
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


def test_ordinal_transcription() -> None:
    """Test number to written ordinal conversion."""

    from speech.trans.num import number_to_ordinal, numbers_to_ordinal

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


def test_float_transcription() -> None:
    """Test float to written text conversion."""

    from speech.trans.num import float_to_text, floats_to_text

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
        float_to_text("-10.100,21")
        == float_to_text("-10100,21")
        == float_to_text("-10100.21")
        == "mínus tíu þúsund og eitt hundrað komma tuttugu og eitt"
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


def test_digit_transcription() -> None:
    """Test digit string to written text conversion."""

    from speech.trans.num import digits_to_text

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


def test_time_transcription() -> None:
    assert DT.time(f"00:00") == "tólf á miðnætti"
    assert DT.time(f"12:00") == "tólf á hádegi"
    midnight = datetime.time(0, 0)
    six_am = datetime.time(6, 0)
    for h, m in product(range(24), range(60)):
        t = datetime.time(hour=h, minute=m)
        n = DT.time(t.strftime("%H:%M"))
        assert n.replace(" ", "").isalpha()
        if midnight < t < six_am:
            assert "um nótt" in n
    t = datetime.time(6, 6, 6)
    assert "klukkan sex núll sex núll sex" == DT.time(t.strftime("klukkan %H:%M:%S"))
    assert "klukkan sex núll sex núll sex" == DT.time(t.strftime("kl. %H:%M:%S"))
    t = datetime.time(3, 3, 3)
    assert "þrjú núll þrjú núll þrjú um nótt" == DT.time(t.strftime("%H:%M:%S"))


def test_date_transcription() -> None:
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
            n1 = DT.date(date.isoformat(), case=case)
            assert n1 == DT.date(f"{y}-{m}-{d}", case=case)
            n2 = DT.date(f"{d}/{m}/{y}", case=case)
            assert n2 == DT.date(date.strftime("%d/%m/%Y"), case=case)
            n3 = DT.date(date.strftime("%d. %B %Y"), case=case)
            n4 = DT.date(date.strftime("%d. %b %Y"), case=case)
            assert n1 == n2 == n3 == n4


def test_spelling_transcription() -> None:
    from speech.trans import _ICE_ENG_ALPHA

    _ALPHABET = _ICE_ENG_ALPHA + _ICE_ENG_ALPHA.lower()

    for a in (_ALPHABET, "ÁÍS", "BSÍ", "LSH", "SÍBS"):
        n1 = DT.spell(a.upper())
        n2 = DT.spell(a.lower())
        assert n1 == n2
        assert "." not in re.sub(r"<break .*?/>", "", n1)
        assert len(n1) > len(a)
        assert n1.islower()


def test_abbreviation_transcription() -> None:
    abbrevs = (
        "t.d.",
        "MSc",
        "m.a.s.",
        "o.s.frv.",
        "m.a.",
        "PhD",
        "Ph.D.",
    )
    for a in abbrevs:
        n = DT.abbrev(a)
        assert "." not in re.sub(r"<break .*?/>", "", n)
        assert n.islower()


def test_email_transcription() -> None:
    for e in (
        "jon.jonsson@mideind.is",
        "gunnar.brjann@youtube.gov.uk",
        "tolvupostur@gmail.com",
    ):
        n = DT.email(e)
        assert "@" not in n and " hjá " in n
        assert "." not in re.sub(r"<break .*?/>", "", n) and " punktur " in n


def test_entity_transcription() -> None:
    n = DT.entity("Miðeind ehf.")
    assert "ehf." not in n
    n = DT.entity("BSÍ")
    assert "BSÍ" not in n
    n = DT.entity("SÍBS")
    assert "SÍBS" not in n
    n = DT.entity("L&L slf.")
    assert "L" not in n
    assert "slf" not in n
    n = DT.entity("Kjarninn")
    assert n == "Kjarninn"
    n = DT.entity("RANNÍS")
    assert n.upper() == "RANNÍS"
    n = DT.entity("Rannís")
    assert n == "Rannís"
    n = DT.entity("Verkís")
    assert n == "Verkís"
    n = DT.entity("RARIK")
    assert n == "RARIK"
    n = DT.entity("NATO")
    assert n == "NATO"
    n = DT.entity("NASA")
    assert n.upper() == "NASA"
    n = DT.entity("Víkurskel ehf.")
    assert n.startswith("Víkurskel") and "ehf." not in n
    n = DT.entity("VF 45 ehf.")
    assert "VF" not in n and "ehf." not in n and "45" not in n
    n = DT.entity("Alþjóðalyfjaeftirlitsstofnunin")
    assert n == "Alþjóðalyfjaeftirlitsstofnunin"
    n = DT.entity("ÖSE")
    assert n != "ÖSE"
    n = DT.entity("Ungmennaráð UMFÍ")
    assert n.startswith("Ungmennaráð") and "UMFÍ" not in n
    n = DT.entity("NEC Nijmegen")
    assert "NEC" not in n and n.endswith("Nijmegen")
    n = DT.entity("Fabienne Buccio")
    assert n == "Fabienne Buccio"
    n = DT.entity("Salgado")
    assert n == "Salgado"
    n = DT.entity("Sleep Inn")
    assert n == "Sleep Inn"
    n = DT.entity("GSMbensín")
    assert n == "GSMbensín"
    n = DT.entity("Kvennalistinn.is")
    assert n == "Kvennalistinn.is"
    n = DT.entity("USS Comfort")
    assert "USS" not in n and n.endswith("Comfort")
    n = DT.entity("Bayern München - FC Rostov")
    assert "FC" not in n


def test_generic_transcription() -> None:
    n = DT.generic("þjálfari ÍR")
    assert "ÍR" not in n and "þjálfari " in n
    n = DT.generic("fulltrúi í samninganefnd félagsins")
    assert n == "fulltrúi í samninganefnd félagsins"
    n = DT.generic("formaður nefndarinnar")
    assert n == "formaður nefndarinnar"
    n = DT.generic("fyrrverandi Bandaríkjaforseti")
    assert n == "fyrrverandi Bandaríkjaforseti"
    n = DT.generic("þjálfari Fram í Olís deild karla")
    assert n == "þjálfari Fram í Olís deild karla"
    n = DT.generic("NASF")
    assert n and "NASF" not in n
    n = DT.generic("íþróttakennari")
    assert n == "íþróttakennari"
    n = DT.generic("formaður Bandalags háskólamanna")
    assert n == "formaður Bandalags háskólamanna"
    n = DT.generic("formaður Leigjendasamtakanna")
    assert n == "formaður Leigjendasamtakanna"
    n = DT.generic("framkvæmdastjóri Samtaka atvinnulífsins (SA)")
    assert "framkvæmdastjóri Samtaka atvinnulífsins" in n and "SA" not in n
    n = DT.generic("innanríkisráðherra í stjórn Sigmundar Davíðs Gunnlaugssonar")
    assert n == "innanríkisráðherra í stjórn Sigmundar Davíðs Gunnlaugssonar"
    n = DT.generic("fyrsti ráðherra Íslands")
    assert n == "fyrsti ráðherra Íslands"
    n = DT.generic("málpípur þær")
    assert n == "málpípur þær"
    n = DT.generic("sundsérfræðingur RÚV")
    assert n == "sundsérfræðingur RÚV"
    n = DT.generic("framkvæmdastjóri Strætó ehf.")
    assert "framkvæmdastjóri Strætó" in n and "ehf." not in n
    n = DT.generic("þáverandi sjávarútvegsráðherra")
    assert n == "þáverandi sjávarútvegsráðherra"
    n = DT.generic("knattspyrnudómari")
    assert n == "knattspyrnudómari"
    n = DT.generic("framkvæmdastjóri Félags atvinnurekenda")
    assert n == "framkvæmdastjóri Félags atvinnurekenda"
    n = DT.generic("þjálfari Stjörnunnar")
    assert n == "þjálfari Stjörnunnar"
    n = DT.generic("lektor við HÍ")
    assert "lektor við" in n and "HÍ" not in n
    n = DT.generic("formaður VR og LÍV")
    assert "formaður" in n and "VR" not in n and "LÍV" not in n
    # Test complete_text arg
    n = DT.generic("trillukarl í Skerjafirði")
    assert n == "trillukarl í Skerjafirði"
    n = DT.generic("trillukarl í Skerjafirði", full_text=True)
    assert n == "<p><s>trillukarl í Skerjafirði</s></p>"

    # Replace whitespace with single space in text
    # stretching over multiple lines
    ws_re = re.compile(r"\n\s+")
    ws_to_space: Callable[[str], str] = lambda t: ws_re.sub(" ", t.strip())
    t = ws_to_space(
        """
        Breski seðlabankinn hækkaði stýrivexti sína í dag
        um hálft prósentustig og eru vextir nú yfir 3,2%.
        Það eru hæstu stýrivextir í Bretlandi í 14 ár.
        Seðlabankinn vonar að vaxtahækkunin stemmi stigu
        við mikilli verðbólgu í landinu.
        """
    )
    n = DT.generic(t, full_text=True)
    assert "fjórtán" in n and "yfir þrjú komma tvö prósent" in n
    t = ws_to_space(
        """
        Breski seðlabankinn hækkaði stýrivexti sína í dag
        um hálft prósentustig og eru vextir nú yfir 3,2 prósentum.
        Það eru hæstu stýrivextir í Bretlandi í 14 ár.
        Seðlabankinn vonar að vaxtahækkunin stemmi stigu
        við mikilli verðbólgu í landinu.
        """
    )
    n = DT.generic(t, full_text=True)
    assert "fjórtán" in n and "yfir þremur komma tveimur prósentum" in n
    t = ws_to_space(
        """
        t.d. var 249% munur á ódýrstu og dýrustu rauðrófunum,
        118% munur milli bökunarkartafla, 291% munur á grænum eplum,
        97% munur á vínberjum og 2-3% af jarðarberjum.
        """
    )
    n = DT.generic(t, full_text=True)
    assert (
        "%" not in n
        and "til dæmis" in n
        and "tvö hundruð níutíu og eitt prósent" in n
        and "tvö til þrjú prósent"
    )
    n = DT.generic(
        "sagðist hún vona að á næstu 10-20 árum "
        "yrði farið að nýta tæknina 9,2-5,3 prósent meira."
    )
    assert (
        "tíu til tuttugu árum" in n and "níu komma tvö til fimm komma þrjú prósent" in n
    )
    t = ws_to_space(
        """
        Frakkland - Marókkó á HM.
        Leikurinn var bráðfjörugur en það voru Frakkar
        sem voru sterkari og unnu þeir leikinn 2-0.
        """
    )
    n = DT.generic(t, full_text=True)
    assert "Frakkland til Marókkó" not in n and "HM" not in n and "tvö núll" in n
    t = ws_to_space(
        """
        2 eru slasaðir og um 1.500 fiskar dauðir eftir að um
        16 metra hátt fiskabúr í miðju Radisson hóteli
        í Berlín sprakk snemma í morgun.
        """
    )
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert "tveir" in n and "eitt þúsund og fimm hundruð" in n and "sextán metra" in n

    t = ws_to_space("Fréttin var síðast uppfærð 3/12/2022 kl. 10:42.")
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert (
        "þriðja desember tvö þúsund tuttugu og tvö" in n
        and "klukkan tíu fjörutíu og tvö" in n
    )
    t = ws_to_space("Fréttin var síðast uppfærð 16. desember 2022 kl. 10:42.")
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert (
        "sextánda desember tvö þúsund tuttugu og tvö" in n
        and "klukkan tíu fjörutíu og tvö" in n
    )
    t = ws_to_space("Fréttin var síðast uppfærð 2. janúar 2022.")
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert "annan janúar tvö þúsund tuttugu og tvö" in n
    t = ws_to_space("Fréttin var síðast uppfærð 01/01/2022.")
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert "fyrsta janúar tvö þúsund tuttugu og tvö" in n
    t = ws_to_space("Fréttin var síðast uppfærð 14. nóvember og 16. desember 1999.")
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert "fjórtánda nóvember og sextánda desember nítján hundruð níutíu og níu" in n
    t = ws_to_space("Fréttin var síðast uppfærð 2. febrúar klukkan 13:30.")
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert "annan febrúar klukkan þrettán þrjátíu" in n

    t = ws_to_space(
        """
        „ICELAND-málið er mikilvægt og fordæmisgefandi bæði á sviði
        hugverkaréttar og þjóðaréttar enda getur niðurstaða þess leitt
        til breytinga á evrópskum hugverkarétti.
        Athygli hefur vakið að áfrýjunarnefnd EUIPO er að þessu sinni
        fjölskipuð, þ.e. skipuð níu aðilum í stað þriggja eins og í
        hefðbundnum áfrýjunarnefndum. Það er talið til marks um hve
        mikilvægt málið er talið vera, en af um það bil 2.500 árlegum
        áfrýjunum er einungis 3-5 vísað til fjölskipaðrar áfrýjunarnefndar.
        Þegar við bætist að málið er það fyrsta sem flutt er munnlega fyrir
        nefndinni verður þýðing þess enn betur ljós,“ segir á vef Stjórnarráðsins.
        """
    )
    n = DT.generic(t, full_text=True)
    assert n.startswith("<p><s>") and n.endswith("</s></p>")
    assert "hugverkarétti" in n
    assert "ICELAND" in n and "EUIPO" not in n
    assert "það er" in n and "þ.e." not in n
    assert "2.500" not in n and "tvö þúsund og fimm hundruð árlegum áfrýjunum"
    # assert "þremur til fimm" in n # TODO


def test_person_transcription() -> None:
    # Roman numerals
    n = DT.person("Elísabet II")
    assert n == "Elísabet önnur"
    n = DT.person("Elísabet II Bretlandsdrottning")
    assert n == "Elísabet önnur Bretlandsdrottning"
    n = DT.person("Leópold II Belgakonungur")
    assert n == "Leópold annar Belgakonungur"
    n = DT.person("Óskar II Svíakonungur")
    assert n == "Óskar annar Svíakonungur"
    n = DT.person("Loðvík XVI")
    assert n == "Loðvík sextándi"

    # Normal
    n = DT.person("Einar Björn")
    assert n == "Einar Björn"
    n = DT.person("Martin Rivers")
    assert n == "Martin Rivers"
    n = DT.person("Tor Magne Drønen")
    assert n == "Tor Magne Drønen"
    n = DT.person("Richard Guthrie")
    assert n == "Richard Guthrie"
    n = DT.person("Jón Ingvi Bragason")
    assert n == "Jón Ingvi Bragason"
    n = DT.person("Regína Valdimarsdóttir")
    assert n == "Regína Valdimarsdóttir"
    n = DT.person("Sigurður Ingvi Snorrason")
    assert n == "Sigurður Ingvi Snorrason"
    n = DT.person("Aðalsteinn Sigurgeirsson")
    assert n == "Aðalsteinn Sigurgeirsson"

    # Abbreviations which should be spelled out
    # Note that the spelling can be different based on the voice engine
    n = DT.person("James H. Grendell")
    assert "H." not in n and n.startswith("James") and n.endswith("Grendell")
    n = DT.person("Guðni Th. Jóhannesson")
    assert "Th" not in n and n.startswith("Guðni") and n.endswith("Jóhannesson")
    n = DT.person("guðni th. jóhannesson")
    assert "th" not in n and n.startswith("guðni") and n.endswith("jóhannesson")
    n = DT.person("Mary J. Blige")
    assert "J." not in n and n.startswith("Mary") and n.endswith("Blige")
    n = DT.person("Alfred P. Sloan Jr.")
    assert "P." not in n and "Jr." not in n and "Alfred" in n and "Sloan" in n

    # Lowercase middle names
    assert DT.person("Louis van Gaal") == "Louis van Gaal"
    assert DT.person("Frans van Houten") == "Frans van Houten"
    assert DT.person("Alex van der Zwaan") == "Alex van der Zwaan"
    assert DT.person("Rafael van der Vaart") == "Rafael van der Vaart"


def test_voice_breaks() -> None:
    assert DT.vbreak() == "<break />"
    for t in ("0ms", "50ms", "1s", "1.7s"):
        n = DT.vbreak(time=t)
        assert n == f'<break time="{t}" />'
    for s in DT._VBREAK_STRENGTHS:
        n = DT.vbreak(strength=s)
        assert n == f'<break strength="{s}" />'
