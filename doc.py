"""
    Reynir: Natural language processing for Icelandic

    Copyright (c) 2018 Miðeind ehf.

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


    This module contains code to handle documents such as rtf and docx.

"""

import abc
from io import BytesIO
from zipfile import ZipFile
from pathlib import Path
from bs4 import BeautifulSoup


class Document(abc.ABC):
    """ Abstract base class for documents. """

    def __init__(self, filepath_or_data):
        if isinstance(filepath_or_data, str):
            # It's a file path
            with open(filepath_or_data, "rb") as file:
                self.data = BytesIO(file.read())
        else:
            # It's a byte stream
            self.data = filepath_or_data._file

        print(type(filepath_or_data))
        print(type(self.data))

    @abc.abstractmethod
    def extract_text(self):
        pass

    def write_to_file(self, path):
        raise NotImplementedError


class PlainTextDocument(Document):
    """ Plain text document """

    def extract_text(self):
        raise NotImplementedError


class RTFDocument(Document):
    """ Rich text document """

    def extract_text(self):
        raise NotImplementedError


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

    def __init__(self, filepath_or_data):

        # if isinstance(filepath_or_data, str):
        #     # It's a file.
        #     with open(filepath_or_data, "rb") as file:
        #         self.data = BytesIO(file.read())
        # else:  # Byte stream
        #     self.data = filepath_or_data._file
        super().__init__(filepath_or_data)

        self.zip = ZipFile(self.data, "r")

        # document.xml
        doc_bytes = self.zip.read(self.DOCXML_PATH)
        self.doc_xml = doc_bytes.decode("utf-8")
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
    "application/rtf": RTFDocument,
    "application/pdf": PDFDocument,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DocxDocument,
}

SUPPORTED_DOC_MIMETYPES = frozenset(MIMETYPE_TO_DOC_CLASS.keys())
