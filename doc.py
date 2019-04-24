"""
    Reynir: Natural language processing for Icelandic

    Copyright (c) 2019 Miðeind ehf.

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


    This module contains code to manipulate and extract text from documents 
    such as plain text, html, rtf and docx files.

"""

import abc
from io import BytesIO
import re
from zipfile import ZipFile
from pathlib import Path
from bs4 import BeautifulSoup
import html2text


DEFAULT_TEXT_ENCODING = "UTF-8"


class Document(abc.ABC):
    """ Abstract base class for documents. """

    def __init__(self, path_or_bytes):
        """ Accepts either a file path or bytes object """
        if isinstance(path_or_bytes, str):
            # It's a file path
            with open(path_or_bytes, "rb") as file:
                self.data = file.read()
        else:
            # It's a byte stream
            self.data = path_or_bytes

    @abc.abstractmethod
    def extract_text(self):
        """ All subclasses must implement this method """
        pass

    def write_to_file(self, path):
        with open(path, 'wb') as f:
            f.write(self.data)


class PlainTextDocument(Document):
    """ Plain text document """

    def extract_text(self):
        return self.data.decode(DEFAULT_TEXT_ENCODING)


class HTMLDocument(Document):
    """ HTML document """

    @staticmethod
    def remove_header_prefixes(text):
        """ Removes all line starting with '#'. Annoyingly, html2text 
            adds markdown-style headers for <h*> tags """
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("#"):
                lines[i] = re.sub(r"[#]+\s", "", line)
        return "\n".join(lines)

    def extract_text(self):
        html = self.data.decode(DEFAULT_TEXT_ENCODING)

        h = html2text.HTML2Text()
        # See https://github.com/Alir3z4/html2text/blob/master/html2text/cli.py
        h.ignore_links = True
        h.ignore_emphasis = True
        h.ignore_images = True
        h.unicode_snob = True
        h.ignore_tables = True
        h.decode_errors = "ignore"

        text = h.handle(html)

        return self.remove_header_prefixes(text)

    # def extract_text(self):
    #     soup = BeautifulSoup(self.data, features="html.parser")
    #     try:
    #         body = soup.find("body")
    #         clean_text = " ".join(body.stripped_strings)
    #     except:
    #         return ""
    #     return clean_text


class RTFDocument(Document):
    """ Rich text document """

    def extract_text(self):
        return self.strip_rtf(self.data)

    def strip_rtf(self, text):
        """ Extract plain text from RTF.
            Source: http://stackoverflow.com/a/188877
            Code created by Markus Jarderot: http://mizardx.blogspot.com
        """

        pattern = re.compile(
            r"\\([a-z]{1,32})(-?\d{1,10})?[ ]?|\\'([0-9a-f]{2})|\\([^a-z])|([{}])|[\r\n]+|(.)",
            re.I,
        )

        # Control words which specify a "destination".
        destinations = frozenset(
            (
                "aftncn",
                "aftnsep",
                "aftnsepc",
                "annotation",
                "atnauthor",
                "atndate",
                "atnicn",
                "atnid",
                "atnparent",
                "atnref",
                "atntime",
                "atrfend",
                "atrfstart",
                "author",
                "background",
                "bkmkend",
                "bkmkstart",
                "blipuid",
                "buptim",
                "category",
                "colorschememapping",
                "colortbl",
                "comment",
                "company",
                "creatim",
                "datafield",
                "datastore",
                "defchp",
                "defpap",
                "do",
                "doccomm",
                "docvar",
                "dptxbxtext",
                "ebcend",
                "ebcstart",
                "factoidname",
                "falt",
                "fchars",
                "ffdeftext",
                "ffentrymcr",
                "ffexitmcr",
                "ffformat",
                "ffhelptext",
                "ffl",
                "ffname",
                "ffstattext",
                "field",
                "file",
                "filetbl",
                "fldinst",
                "fldrslt",
                "fldtype",
                "fname",
                "fontemb",
                "fontfile",
                "fonttbl",
                "footer",
                "footerf",
                "footerl",
                "footerr",
                "footnote",
                "formfield",
                "ftncn",
                "ftnsep",
                "ftnsepc",
                "g",
                "generator",
                "gridtbl",
                "header",
                "headerf",
                "headerl",
                "headerr",
                "hl",
                "hlfr",
                "hlinkbase",
                "hlloc",
                "hlsrc",
                "hsv",
                "htmltag",
                "info",
                "keycode",
                "keywords",
                "latentstyles",
                "lchars",
                "levelnumbers",
                "leveltext",
                "lfolevel",
                "linkval",
                "list",
                "listlevel",
                "listname",
                "listoverride",
                "listoverridetable",
                "listpicture",
                "liststylename",
                "listtable",
                "listtext",
                "lsdlockedexcept",
                "macc",
                "maccPr",
                "mailmerge",
                "maln",
                "malnScr",
                "manager",
                "margPr",
                "mbar",
                "mbarPr",
                "mbaseJc",
                "mbegChr",
                "mborderBox",
                "mborderBoxPr",
                "mbox",
                "mboxPr",
                "mchr",
                "mcount",
                "mctrlPr",
                "md",
                "mdeg",
                "mdegHide",
                "mden",
                "mdiff",
                "mdPr",
                "me",
                "mendChr",
                "meqArr",
                "meqArrPr",
                "mf",
                "mfName",
                "mfPr",
                "mfunc",
                "mfuncPr",
                "mgroupChr",
                "mgroupChrPr",
                "mgrow",
                "mhideBot",
                "mhideLeft",
                "mhideRight",
                "mhideTop",
                "mhtmltag",
                "mlim",
                "mlimloc",
                "mlimlow",
                "mlimlowPr",
                "mlimupp",
                "mlimuppPr",
                "mm",
                "mmaddfieldname",
                "mmath",
                "mmathPict",
                "mmathPr",
                "mmaxdist",
                "mmc",
                "mmcJc",
                "mmconnectstr",
                "mmconnectstrdata",
                "mmcPr",
                "mmcs",
                "mmdatasource",
                "mmheadersource",
                "mmmailsubject",
                "mmodso",
                "mmodsofilter",
                "mmodsofldmpdata",
                "mmodsomappedname",
                "mmodsoname",
                "mmodsorecipdata",
                "mmodsosort",
                "mmodsosrc",
                "mmodsotable",
                "mmodsoudl",
                "mmodsoudldata",
                "mmodsouniquetag",
                "mmPr",
                "mmquery",
                "mmr",
                "mnary",
                "mnaryPr",
                "mnoBreak",
                "mnum",
                "mobjDist",
                "moMath",
                "moMathPara",
                "moMathParaPr",
                "mopEmu",
                "mphant",
                "mphantPr",
                "mplcHide",
                "mpos",
                "mr",
                "mrad",
                "mradPr",
                "mrPr",
                "msepChr",
                "mshow",
                "mshp",
                "msPre",
                "msPrePr",
                "msSub",
                "msSubPr",
                "msSubSup",
                "msSubSupPr",
                "msSup",
                "msSupPr",
                "mstrikeBLTR",
                "mstrikeH",
                "mstrikeTLBR",
                "mstrikeV",
                "msub",
                "msubHide",
                "msup",
                "msupHide",
                "mtransp",
                "mtype",
                "mvertJc",
                "mvfmf",
                "mvfml",
                "mvtof",
                "mvtol",
                "mzeroAsc",
                "mzeroDesc",
                "mzeroWid",
                "nesttableprops",
                "nextfile",
                "nonesttables",
                "objalias",
                "objclass",
                "objdata",
                "object",
                "objname",
                "objsect",
                "objtime",
                "oldcprops",
                "oldpprops",
                "oldsprops",
                "oldtprops",
                "oleclsid",
                "operator",
                "panose",
                "password",
                "passwordhash",
                "pgp",
                "pgptbl",
                "picprop",
                "pict",
                "pn",
                "pnseclvl",
                "pntext",
                "pntxta",
                "pntxtb",
                "printim",
                "private",
                "propname",
                "protend",
                "protstart",
                "protusertbl",
                "pxe",
                "result",
                "revtbl",
                "revtim",
                "rsidtbl",
                "rxe",
                "shp",
                "shpgrp",
                "shpinst",
                "shppict",
                "shprslt",
                "shptxt",
                "sn",
                "sp",
                "staticval",
                "stylesheet",
                "subject",
                "sv",
                "svb",
                "tc",
                "template",
                "themedata",
                "title",
                "txe",
                "ud",
                "upr",
                "userprops",
                "wgrffmtfilter",
                "windowcaption",
                "writereservation",
                "writereservhash",
                "xe",
                "xform",
                "xmlattrname",
                "xmlattrvalue",
                "xmlclose",
                "xmlname",
                "xmlnstbl",
                "xmlopen",
            )
        )

        # Translation of some special characters.
        specialchars = {
            "par": "\n",
            "sect": "\n\n",
            "page": "\n\n",
            "line": "\n",
            "tab": "\t",
            "emdash": "\u2014",
            "endash": "\u2013",
            "emspace": "\u2003",
            "enspace": "\u2002",
            "qmspace": "\u2005",
            "bullet": "\u2022",
            "lquote": "\u2018",
            "rquote": "\u2019",
            "ldblquote": "\201C",
            "rdblquote": "\u201D",
        }

        stack = []
        ignorable = False  # Whether this group (and all inside it) are "ignorable".
        ucskip = 1  # Number of ASCII characters to skip after a unicode character.
        curskip = 0  # Number of ASCII characters left to skip
        out = []  # Output buffer.

        for match in pattern.finditer(text.decode()):
            word, arg, hex, char, brace, tchar = match.groups()
            if brace:
                curskip = 0
                if brace == "{":
                    # Push state
                    stack.append((ucskip, ignorable))
                elif brace == "}":
                    # Pop state
                    ucskip, ignorable = stack.pop()
            elif char:  # \x (not a letter)
                curskip = 0
                if char == "~":
                    if not ignorable:
                        out.append("\xA0")
                elif char in "{}\\":
                    if not ignorable:
                        out.append(char)
                elif char == "*":
                    ignorable = True
            elif word:  # \foo
                curskip = 0
                if word in destinations:
                    ignorable = True
                elif ignorable:
                    pass
                elif word in specialchars:
                    out.append(specialchars[word])
                elif word == "uc":
                    ucskip = int(arg)
                elif word == "u":
                    c = int(arg)
                    if c < 0:
                        c += 0x10000
                    if c > 127:
                        out.append(chr(c))  # NOQA
                    else:
                        out.append(chr(c))
                    curskip = ucskip
            elif hex:  # \'xx
                if curskip > 0:
                    curskip -= 1
                elif not ignorable:
                    c = int(hex, 16)
                    if c > 127:
                        out.append(chr(c))  # NOQA
                    else:
                        out.append(chr(c))
            elif tchar:
                if curskip > 0:
                    curskip -= 1
                elif not ignorable:
                    out.append(tchar)
        return "".join(out)


class PDFDocument(Document):
    """ Adobe PDF document """

    def extract_text(self):
        raise NotImplementedError


class DocxDocument(Document):
    """ Microsoft docx document """

    COMMENTS_AUTHOR = "Greynir"
    DOCXML_PATH = "word/document.xml"
    COMXML_PATH = "word/comments.xml"
    MODIFIED = frozenset((DOCXML_PATH, COMXML_PATH))

    def __init__(self, path_or_bytes):
        super().__init__(path_or_bytes)

        self.zip = ZipFile(BytesIO(self.data), "r")

        # document.xml
        doc_bytes = self.zip.read(self.DOCXML_PATH)
        self.doc_xml = doc_bytes.decode(DEFAULT_TEXT_ENCODING)
        self.doc_soup = BeautifulSoup(self.doc_xml, "lxml-xml")

        # comments.xml
        # comments_bytes = self.zip.read(self.COMXML_PATH)
        # self.comments_xml = comments_bytes.decode("utf-8")
        # self.comments_soup = BeautifulSoup(self.comments_xml, "lxml-xml")

    def extract_text(self):

        soup = BeautifulSoup(self.doc_xml, "lxml-xml")
        if soup is None:
            return None

        paragraphs = soup.find_all("w:p")
        text = "\n".join(p.text for p in paragraphs)

        return text

    # def next_comment_id(self):
    #     highest = -1
    #     for c in self.comments_soup.find_all("w:comment"):
    #         idstr = c.get("w:id")
    #         try:
    #             idint = int(idstr)
    #             highest = max(highest, idint)
    #         except:
    #             pass

    #     return highest + 1

    # def annotate(self, comments):

    #     comments_elm = self.comments_soup.find("w:comments")
    #     next_id = self.next_comment_id()
    #     paragraphs = self.doc_soup.find_all("w:p")

    #     for c in comments:

    #         # First, append comment objects to comments.xml
    #         elm = '\
    #         <w:comment xmlns:w="https://ss" w:author="{0}" w:date="{1}" w:id="{2}" w:initials="{3}"> \
    #             <w:p> \
    #                 <w:pPr> \
    #                     <w:pStyle w:val="CommentText"/> \
    #                 </w:pPr> \
    #                 <w:r> \
    #                     <w:rPr> \
    #                         <w:rStyle w:val="CommentReference"/> \
    #                     </w:rPr> \
    #                     <w:annotationRef/> \
    #                 </w:r> \
    #                 <w:r> \
    #                     <w:t>{4}</w:t> \
    #                 </w:r> \
    #             </w:p> \
    #         </w:comment>'.format(
    #             COMMENTS_AUTHOR, "", str(next_id), COMMENTS_AUTHOR[:1], c["text"]
    #         )
    #         # comments_elm.append(BeautifulSoup(elm, "lxml-xml"))

    #         # Add references to comments for the specified range in document.xml
    #         if c["p"] > len(paragraphs) - 1:
    #             print("Outside paragraph range")
    #             continue

    #         # for p in paragraphs:
    #         #     print(p)

    #         # p = paragraphs[int(c["p"])]

    #         # start = self.doc_soup.new_tag("w:commentRangeStart")
    #         # start["w:id"] = str(next_id)

    #         # end = self.doc_soup.new_tag("w:commentRangeEnd")
    #         # end["w:id"] = str(next_id)

    #         # p.insert(0, start)
    #         # p.append(end)

    #         next_id += 1

    #     print(self.doc_soup)

    # def write_to_file(self, path):
    #     # Python's zip module doesn't allow overwriting or removing
    #     # files from an archive so we create a new one.
    #     outzip = ZipFile(path, "x")

    #     # Copy over all unmodified files
    #     for m in self.zip.namelist():
    #         if m not in MODIFIED:
    #             mbytes = self.zip.read(m)
    #             outzip.writestr(m, mbytes)

    #     # Write modified files
    #     outzip.writestr(self.DOCXML_PATH, str(self.doc_soup))
    #     outzip.writestr(self.COMXML_PATH, str(self.comments_soup))

    #     outzip.close()


# Map file mime type to document class
MIMETYPE_TO_DOC_CLASS = {
    "text/plain": PlainTextDocument,
    "text/html": HTMLDocument,
    "text/rtf": RTFDocument,
    "application/rtf": RTFDocument,
    # "application/pdf": PDFDocument,
    # "application/application/x-pdf": PDFDocument,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxDocument,
}

SUPPORTED_DOC_MIMETYPES = frozenset(MIMETYPE_TO_DOC_CLASS.keys())
