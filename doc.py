"""
    Greynir: Natural language processing for Icelandic

    Copyright (C) 2020 Miðeind ehf.

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


    This module contains code to extract text from documents
    such as plain text, html, rtf and docx files.

"""

import abc
from io import BytesIO
import re
from zipfile import ZipFile
import html2text
from striprtf.striprtf import rtf_to_text

# Use defusedxml module to prevent parsing of malicious XML
from defusedxml import ElementTree


DEFAULT_TEXT_ENCODING = "UTF-8"


class MalformedDocumentError(Exception):
    pass


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
        with open(path, "wb") as f:
            f.write(self.data)


class PlainTextDocument(Document):
    """ Plain text document """

    def extract_text(self):
        return self.data.decode(DEFAULT_TEXT_ENCODING)


class HTMLDocument(Document):
    """ HTML document """

    @staticmethod
    def _remove_header_prefixes(text):
        """ Removes '#' in all lines starting with '#'. Annoyingly,
            html2text adds markdown-style headers for <h*> tags. """
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
        h.body_width = 0

        text = h.handle(html)

        return self._remove_header_prefixes(text)


class RTFDocument(Document):
    """ Rich text document """

    def extract_text(self):
        txt = self.data.decode(DEFAULT_TEXT_ENCODING)

        # Hack to handle Apple's extensions to the RTF format
        txt = txt.replace("\\\n\\\n", "\\\n\\par\n")

        return rtf_to_text(txt)


class PDFDocument(Document):
    """ Adobe PDF document """

    def extract_text(self):
        raise NotImplementedError


class DocxDocument(Document):
    """ Microsoft docx document """

    DOCXML_PATH = "word/document.xml"
    WORD_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    PARAGRAPH_TAG = WORD_NAMESPACE + "p"
    TEXT_TAG = WORD_NAMESPACE + "t"
    BREAK_TAG = WORD_NAMESPACE + "br"

    def extract_text(self):

        zipfile = ZipFile(BytesIO(self.data), "r")

        # Verify that archive contains document.xml
        if self.DOCXML_PATH not in zipfile.namelist():
            raise MalformedDocumentError("Malformed docx file")

        # Read xml file from archive
        content = zipfile.read(self.DOCXML_PATH)
        zipfile.close()

        # Parse it
        tree = ElementTree.fromstring(content)

        # Extract text elements from all paragraphs
        # (with special handling of line breaks)
        paragraphs = []
        for p in tree.iter(self.PARAGRAPH_TAG):
            texts = []
            for node in p.iter():
                if node.tag.endswith(self.TEXT_TAG) and node.text:
                    texts.append(node.text)
                elif node.tag.endswith(self.BREAK_TAG):
                    texts.append("\n")
            if texts:
                paragraphs.append("".join(texts))

        return "\n\n".join(paragraphs)


# Map file mime type to document class
MIMETYPE_TO_DOC_CLASS = {
    "text/plain": PlainTextDocument,
    "text/html": HTMLDocument,
    "text/rtf": RTFDocument,
    "application/rtf": RTFDocument,
    # "application/pdf": PDFDocument,
    # "application/x-pdf": PDFDocument,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxDocument,  # Yes, really
}

SUPPORTED_DOC_MIMETYPES = frozenset(MIMETYPE_TO_DOC_CLASS.keys())
