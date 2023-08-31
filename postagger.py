"""

    Greynir: Natural language processing for Icelandic

    POS tagger module

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


    This module implements a wrapper for Greynir's POS tagging
    functionality. It allows clients to simply and cleanly generate POS tags
    from plain text into a Python dict, which can then easily be converted to
    JSON if desired.

    Use as follows:

    from postagger import Tagger

    with Tagger.session() as tagger:
        for text in mytexts:
            d = tagger.tag(text)
            do_something_with(d["result"], d["stats"], d["register"])

    The session() context manager will automatically clean up after the
    tagging session, i.e. release a scraper database session and the
    parser with its memory caches. Tagging multiple sentences within one
    session is much more efficient than creating separate sessions for
    each one.

"""

from typing import (
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    Iterable,
    Iterator,
    Union,
    cast,
)

import math
import os
from collections import defaultdict
from itertools import islice, tee
import xml.etree.ElementTree as ET

from reynir import TOK, tokenize
from reynir.binparser import canonicalize_token
from reynir.bintokenizer import TokenDict
from reynir.ifdtagger import IFD_Tagset
from reynir.settings import Prepositions
from tokenizer.definitions import (
    BIN_Tuple,
    BIN_TupleList,
    PersonNameList,
    PersonNameTuple,
)
from tokenizer.tokenizer import Tok

from treeutil import TreeUtility


class IFD_Corpus:
    """A utility class to access the IFD corpus of XML files, by default
    assumed to be located in the `ifd` directory."""

    def __init__(self, ifd_dir: str = "ifd") -> None:
        self._ifd_full_dir = os.path.join(os.getcwd(), ifd_dir)
        self._xml_files = [
            x
            for x in os.listdir(self._ifd_full_dir)
            if x.startswith("A") and x.endswith(".xml")
        ]
        self._xml_files.sort()

    def number_of_files(
        self, filter_func: Optional[Callable[[str], bool]] = None
    ) -> int:
        """Return the number of files in the corpus after filtering by filter_func, if given"""
        return sum(
            (1 if filter_func is None or filter_func(x) else 0) for x in self._xml_files
        )

    def file_name_stream(
        self, filter_func: Optional[Callable[[str], bool]] = None
    ) -> Iterable[str]:
        """Generator of file names, including paths, eventually filtered by the filter_func"""
        for each in self._xml_files:
            if filter_func is None or filter_func(each):
                filename = os.path.join(self._ifd_full_dir, each)
                yield filename

    def starting_file(self, filename: str, count: int, num_files: int) -> None:
        """Called when xml_stream() starts to read from a new file"""
        # Override in derived classes to provide a progress report, if desired
        pass

    def xml_stream(
        self, filter_func: Optional[Callable[[str], bool]] = None
    ) -> Iterable[ET.Element]:
        """Generator of a stream of XML document roots, eventually filtered by the filter_func"""
        num_files = self.number_of_files(filter_func)
        cnt = 0
        for each in self.file_name_stream(filter_func):
            root = ET.parse(each).getroot()
            if root is not None:
                cnt += 1
                self.starting_file(each, cnt, num_files)
                yield root

    def raw_sentence_stream(
        self,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        filter_func: Optional[Callable[[str], bool]] = None,
    ) -> Iterable[List[Tuple[str, str, str]]]:
        """Generator of sentences from the IFD XML files.
        Each sentence consists of (word, tag, lemma) triples."""
        count = 0
        skipped = 0
        for root in self.xml_stream(filter_func=filter_func):
            for sent in root.iter("s"):
                if len(sent):  # Using a straight Bool test here gives a warning
                    if isinstance(skip, int) and skipped < skip:
                        # If a skip parameter was given, skip that number of sentences up front
                        skipped += 1
                        continue
                    if callable(skip) and skip(count + skipped):
                        # If skip is a function, call it with the number of total sentences seen
                        # and skip this one if it returns True
                        skipped += 1
                        continue
                    yield [
                        (word.text.strip(), word.get("type", ""), word.get("lemma", ""))
                        for word in sent
                        if word.text
                    ]
                    count += 1
                    if limit is not None and count >= limit:
                        return

    def sentence_stream(
        self,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        filter_func: Optional[Callable[[str], bool]] = None,
    ) -> Iterable[List[str]]:
        """Generator of sentences from the IFD XML files.
        Each sentence is a list of words."""
        for sent in self.raw_sentence_stream(limit, skip, filter_func):
            yield [w for (w, _, _) in sent]

    def word_tag_stream(
        self,
        limit: Optional[int] = None,
        skip: Optional[int] = None,
        filter_func: Optional[Callable[[str], bool]] = None,
    ) -> Iterable[List[Tuple[str, str]]]:
        """Generator of sentences from the IFD XML files.
        Each sentence consists of (word, tag) pairs."""
        for sent in self.raw_sentence_stream(limit, skip, filter_func):
            yield [(w, t) for (w, t, _) in sent]


class NgramCounter:
    """A container for the dictionary of known n-grams along with their
    counts. The container can store and load itself from a compact
    text file."""

    def __init__(self) -> None:
        self._d: Dict[Tuple[str, ...], int] = defaultdict(int)

    @property
    def size(self) -> int:
        return len(self._d)

    def add(self, ngram: Tuple[str, ...]) -> None:
        self._d[ngram] += 1

    def count(self, ngram: Tuple[str, ...]) -> int:
        return self._d.get(ngram, 0)

    def store(self, f: TextIO) -> None:
        """Store the ngram dictionary in a compact text format"""
        d = self._d
        vocab: Dict[str, int] = dict()
        # First, store the vocabulary (the distinct ngram tags)
        for ngram in d:
            for w in ngram:
                if w not in vocab:
                    n = len(vocab)
                    vocab[w] = n
        # Store the vocabulary in index order, one per line
        f.write(str(len(vocab)) + "\n")
        f.writelines(
            map(lambda x: x[0] + "\n", sorted(vocab.items(), key=lambda x: x[1]))
        )
        # Store the ngrams and their counts, one per line
        for ngram, cnt in d.items():
            f.write(";".join(str(vocab[w]) for w in ngram) + ";" + str(cnt) + "\n")

    def load(self, f: TextIO) -> None:
        cnt = int(f.readline()[:-1])
        vocab: List[str] = []
        self._d = dict()
        for _ in range(cnt):
            vocab.append(f.readline()[:-1])
        for line in f:
            v = line.split(";")
            v[-1] = v[-1][:-1]
            nv = [int(s) for s in v]
            ngram = tuple(vocab[i] for i in nv[:-1])
            cnt = nv[-1]
            # print("Count of {0} is {1}".format(ngram, cnt))
            self._d[ngram] = cnt


class NgramTagger:
    """A class to assign Icelandic Frequency Dictionary (IFD) tags
    to sentences consisting of 'raw' tokens coming out of the
    tokenizer. A parse tree is not required, so the class can
    also tag sentences for which there is no parse. The tagging
    is based on n-gram and lemma statistics harvested from
    the Greynir article database."""

    CASE_TO_TAG = {"þf": "ao", "þgf": "aþ", "ef": "ae"}

    def __init__(self, n: int = 3, verbose: bool = False) -> None:
        """n indicates the n-gram size, i.e. 3 for trigrams, etc."""
        self.n = n
        self._verbose = verbose
        self.EMPTY = tuple([""] * n)
        # ngram count
        # self.cnt = defaultdict(int)
        self.cnt = NgramCounter()
        # { lemma: { tag : count} }
        self.lemma_cnt: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

    def lemma_tags(self, lemma: str) -> Dict[str, int]:
        """Return a dict of tags and counts for this lemma"""
        return self.lemma_cnt.get(lemma, dict())

    def lemma_count(self, lemma: str) -> int:
        """Return the total occurrence count for a lemma"""
        d = self.lemma_cnt.get(lemma)
        return 0 if d is None else sum(d.values())

    def train(self, sentence_stream: Iterable[Iterable[TokenDict]]):
        """Iterate through a token stream harvested from parsed articles
        and extract tag trigrams"""

        n = self.n

        def tag_stream(sentence_stream: Iterable[Iterable[TokenDict]]) -> Iterator[str]:
            """Generator for tag stream from a token stream"""
            for sent in sentence_stream:
                if not sent:
                    continue
                # For each sentence, start and end with empty strings
                for _ in range(n - 1):
                    yield ""
                for t in sent:
                    tag = None
                    # Skip punctuation
                    if t.get("k", TOK.WORD) != TOK.PUNCTUATION:
                        ct = canonicalize_token(t)
                        tag = str(IFD_Tagset(ct))
                        if tag:
                            self.lemma_cnt[ct.get("x", "")][tag] += 1
                    if tag:
                        yield tag
                for _ in range(n - 1):
                    yield ""

        def ngrams(iterable: Iterable[str]) -> Iterable[Tuple[str, ...]]:
            """Python magic to generate ngram tuples from an iterable input"""
            return zip(
                *((islice(seq, i, None) for i, seq in enumerate(tee(iterable, n))))
            )

        # Count the n-grams
        cnt = self.cnt
        EMPTY = self.EMPTY
        acnt = 0
        for ngram in ngrams(tag_stream(sentence_stream)):
            if ngram != EMPTY:
                cnt.add(ngram)
                acnt += 1
                if self._verbose and acnt % 20000 == 0:
                    # Show progress every 20000 trigrams
                    print(".", end="", flush=True)
        if self._verbose:
            print("", flush=True)

        # Cut off lemma/tag counts <= 1
        lemmas_to_delete: List[str] = []
        for lemma, d in self.lemma_cnt.items():
            tags_to_delete = [tag for tag, cnt in d.items() if cnt == 1]
            for tag in tags_to_delete:
                del d[tag]
            if len(d) == 0:
                lemmas_to_delete.append(lemma)
        for lemma in lemmas_to_delete:
            del self.lemma_cnt[lemma]

        return self

    def store_model(self):
        """Store the model in a pickle file"""
        if self.cnt.size:
            # Don't store an empty count
            with open("ngram-{0}-model.txt".format(self.n), "w") as f:
                f.write(str(len(self.lemma_cnt)) + "\n")

                def lemma_strings():
                    """Generator to convert each lemma_cnt item to a string
                    of the form lemma; tag; count; tag; count; tag; count..."""
                    for lemma, tags in self.lemma_cnt.items():
                        yield "{0};{1}\n".format(
                            lemma,
                            ";".join(tag + ";" + str(cnt) for tag, cnt in tags.items()),
                        )

                f.writelines(lemma_strings())
                self.cnt.store(f)

    def load_model(self):
        """Load the model from a pickle file"""
        with open("ngram-{0}-model.txt".format(self.n), "r") as f:
            cnt = int(f.readline()[:-1])
            self.lemma_cnt = dict()
            for _ in range(cnt):
                line = f.readline()[:-1]
                v = line.split(";")
                # Bit of Python skulduggery to convert a list of the format
                # lemma, tag, count, tag, count, tag, count...
                # to a dictionary of tag:count pairs
                d = dict(zip(v[1::2], (int(n) for n in v[2::2])))
                self.lemma_cnt[v[0]] = d
            self.cnt.load(f)

    def show_model(self):
        """Dump the tag count statistics"""
        print("\nLemmas are {0}".format(len(self.lemma_cnt)))
        print("\nCount contains {0} distinct {1}-grams".format(self.cnt.size, self.n))
        print("\n")

    def _most_likely(
        self, tokens: Sequence[List[Tuple[str, float]]]
    ) -> Tuple[float, List[str]]:
        """Find the most likely tag sequence through the possible tags of each token.
        The tokens are represented by a list of tagset lists, where each tagset list
        entry is a (tag, lexical probability) tuple."""
        cnt = self.cnt
        n = self.n
        history = self.EMPTY
        best_path: List[str] = []
        best_prob: List[float] = []
        len_tokens = len(tokens)

        def fwd_prob(ix: int, history: Tuple[str, ...], fwd: int) -> Tuple[int, float]:
            """Find the most probable tag from the tagset at position `ix`,
            using the history for 'backwards' probability - as well as
            looking forward up to `n - 1` tokens"""
            if self._verbose:
                indent = "  " * (fwd + 1)
            else:
                indent = ""
            if ix >= len_tokens:
                # Looking past the token string: return a log prob of 0.0
                return 0, 0.0
            tagset = tokens[ix]
            prev = history[1:]
            if fwd == 0 and len(tagset) == 1:
                # Short circuit if only one tag is possible
                # Relay the forward probability upwards, unchanged
                if self._verbose:
                    print(
                        indent
                        + "Short circuit as tagset contains only {0}".format(
                            tagset[0][0]
                        )
                    )
                _, fwd_p = fwd_prob(ix + 1, prev + (tagset[0][0],), fwd + 1)
                return 0, fwd_p
            # Sum the number of occurrences of each tag in the tagset, preceded
            # by the given history, plus 1 (meaning that zero occurrences become
            # a count of 1)
            if fwd > 0:
                cnt_tags = len(tagset)
                prev_prev = prev[:-1]
                for prev_tp in tokens[ix - 1]:
                    prev_tag, _ = prev_tp
                    sum_prev = sum(
                        cnt.count(prev_prev + (prev_tag, tag)) for tag, _ in tagset
                    )
                    if self._verbose:
                        print(
                            indent
                            + "Count of {0} + (*) is {1}".format(
                                prev_prev + (prev_tag,), sum_prev
                            )
                        )
                    cnt_tags += sum_prev
                if self._verbose:
                    print(indent + "Total count is {0}".format(cnt_tags))
            else:
                cnt_tags = sum(cnt.count(prev + (tag,)) + 1 for tag, _ in tagset)
            # Calculate a logarithm of the total occurrence count plus the sum of
            # the lexical probabilites of the tags (which is usually 1.0 but may in
            # exceptional circumstances be less)
            log_p_tags = math.log(cnt_tags) + math.log(
                sum(lex_p for _, lex_p in tagset)
            )
            best_ix: Optional[int] = None
            best_prob: Optional[float] = None
            for tag_ix, tp in enumerate(tagset):
                # Calculate the independent probability, given the history, of each
                # tag in the tagset
                tag, lex_p = tp
                ngram = prev + (tag,)
                # Calculate lexical_probability * (tag_count / total_tag_count)
                # in log space
                if self._verbose:
                    print(
                        indent
                        + "Looking at ngram {0} having count {1}".format(
                            ngram, cnt.count(ngram)
                        )
                    )
                log_p_tag = (
                    math.log(lex_p) + math.log(cnt.count(ngram) + 1) - log_p_tags
                )
                if best_prob is not None and log_p_tag < best_prob:
                    # Already too low prob to become the best one: skip this tag
                    if self._verbose:
                        print(
                            indent
                            + "Skipping tag {0} since its log_p {1:.4f} < best_prob {2:.4f}".format(
                                tag, log_p_tag, best_prob
                            )
                        )
                    continue
                # Calculate the forward probability of the next `n - 1 - fwd` tags given
                # that we choose this one
                _, fwd_p = fwd_prob(ix + 1, ngram, fwd + 1) if fwd < n - 1 else (0, 0.0)
                # The total probability we are maximizing is the 'backward' probability
                # of this tag multiplied by the 'forward' probability of the next tags,
                # or `log_p_tag + fwd_p` in log space
                total_p = log_p_tag + fwd_p
                if self._verbose:
                    print(
                        indent
                        + "Tag {0}: lex_p is {1:.4f}, log_p is {2:.4f}, fwd_p is {3:.4f}, total_p {4:.4f}".format(
                            tag, lex_p, log_p_tag, fwd_p, total_p
                        )
                    )
                if best_prob is None or total_p > best_prob:
                    # New maximum probability
                    if self._verbose:
                        print(indent + "New best")
                    best_ix = tag_ix
                    best_prob = total_p
            assert best_ix is not None
            assert best_prob is not None
            return best_ix, best_prob

        for ix, tagset in enumerate(tokens):
            ix_pick, prob = fwd_prob(ix, history, 0)
            pick = tagset[ix_pick][0]
            if self._verbose:
                print(
                    "Index {0}: pick is {1}, prob is {2:.4f}".format(
                        ix, pick, math.exp(prob)
                    )
                )
            best_path.append(pick)
            best_prob.append(prob)
            history = history[1:] + (pick,)

        return math.exp(sum(best_prob)), best_path

    _CONJ_REF = frozenset(["sem", "er"])

    def tag_single_token(self, token: Tok) -> Optional[List[Tuple[str, float]]]:
        """Return a tagset, with probabilities, for a single token"""

        def ifd_tag(kind: int, txt: str, m: BIN_Tuple) -> str:
            i = IFD_Tagset(
                k=TOK.descr[kind],
                c=m.ordfl,
                t=m.ordfl,
                f=m.fl,
                x=txt,
                s=m.stofn,
                b=m.beyging,
            )
            return str(i)

        def ifd_taglist_entity(txt: str) -> List[Tuple[str, float]]:
            i = IFD_Tagset(c="entity", x=txt)
            return [(str(i), 1.0)]

        def ifd_tag_person(txt: str, p: PersonNameTuple):
            i = IFD_Tagset(
                k="PERSON",
                c="person",
                g=p.gender,
                x=txt,
                s=p.name,
                t="person_" + (p.gender or "hk") + ("_" + p.case if p.case else ""),
            )
            return str(i)

        def ifd_taglist_person(
            txt: str, val: PersonNameList
        ) -> List[Tuple[str, float]]:
            s = set(ifd_tag_person(txt, p) for p in val)
            # We simply assume that all possible tags for
            # a person name are equally likely
            prob = 1.0 / len(s)
            return [(tag, prob) for tag in s]

        def ifd_taglist_word(txt: str, mlist: BIN_TupleList) -> List[Tuple[str, float]]:
            if not mlist:
                if txt[0].isupper():
                    # Óþekkt sérnafn?
                    # !!! The probabilities below are a rough guess
                    return [
                        ("nxen-s", 0.6),
                        ("nxeo-s", 0.1),
                        ("nxeþ-s", 0.1),
                        ("nxee-s", 0.2),
                    ]
                # Erlent orð?
                return [("e", 1.0)]
            s = set(ifd_tag(TOK.WORD, txt, m) for m in mlist)
            ltxt = txt.lower()
            if ltxt in Prepositions.PP:
                for case in Prepositions.PP[ltxt]:
                    if case in self.CASE_TO_TAG:
                        s.add(self.CASE_TO_TAG[case])
            if ltxt in self._CONJ_REF:
                # For referential conjunctions,
                # add 'ct' as a possibility (it does not come directly from a BÍN mark)
                s.add("ct")
            # Add a +1 bias to the counts so that no lemma/tag pairs have zero frequency
            prob = self.lemma_count(txt) + len(s)
            d = self.lemma_tags(txt)
            # It is possible for the probabilities of the tags in set s
            # not to add up to 1.0. This can happen if the tokenizer has
            # eliminated certain BÍN meanings due to updated settings
            # in Pref.conf.
            return [(tag, (d.get(tag, 0) + 1) / prob) for tag in s]

        if token.kind == TOK.WORD:
            taglist = ifd_taglist_word(token.txt, token.meanings)
        elif token.kind == TOK.ENTITY:
            taglist = ifd_taglist_entity(token.txt)
        elif token.kind == TOK.PERSON:
            taglist = ifd_taglist_person(token.txt, token.person_names)
        elif token.kind == TOK.NUMBER:
            taglist = [("tfkfn", 1.0)]  # !!!
        elif token.kind == TOK.YEAR:
            taglist = [("ta", 1.0)]
        elif token.kind == TOK.PERCENT:
            taglist = [("tp", 1.0)]
        elif token.kind == TOK.ORDINAL:
            taglist = [("lxexsf", 1.0)]
        # elif token.kind == TOK.CURRENCY:
        #    taglist = None
        # elif token.kind == TOK.AMOUNT:
        #    taglist = None
        # elif token.kind == TOK.DATE:
        #    taglist = None
        elif token.kind == TOK.PUNCTUATION:
            taglist = None
        else:
            print(
                "Unknown tag kind: {0}, text '{1}'".format(
                    TOK.descr[token.kind], token.txt
                )
            )
            taglist = None
        return taglist

    def tag(self, toklist_or_text: Union[str, List[Tok]]) -> List[TokenDict]:
        """Assign IFD tags to the given toklist, putting the tag in the
        "i" field of each non-punctuation token. If a string is passed,
        tokenize it first. Return the toklist so modified."""
        toklist: List[Tok]
        if isinstance(toklist_or_text, str):
            toklist = list(tokenize(toklist_or_text))
        else:
            toklist = list(toklist_or_text)

        tagsets: List[List[Tuple[str, float]]] = []
        for t in toklist:
            if not t.txt:
                continue
            taglist = self.tag_single_token(t)
            if taglist:
                #    display = " | ".join("{0} {1:.2f}".format(w, p) for w, p in taglist)
                #    print("{0:20}: {1}".format(t.txt, display))
                tagsets.append(taglist)

        _, tags = self._most_likely(tagsets)

        if not tags:
            return []

        def gen_tokens() -> Iterable[TokenDict]:
            """Generate a Greynir token sequence from a tagging result"""
            ix = 0
            for t in toklist:
                if not t.txt:
                    continue
                # The code below should correspond to TreeUtility._describe_token()
                d = TokenDict(x=t.txt)
                if t.kind == TOK.WORD:
                    # set d["m"] to the meaning
                    pass
                else:
                    d["k"] = t.kind
                if t.val is not None and t.kind not in {
                    TOK.WORD,
                    TOK.ENTITY,
                    TOK.PUNCTUATION,
                }:
                    # For tokens except words, entities and punctuation, include the val field
                    if t.kind == TOK.PERSON:
                        d["v"], d["g"] = TreeUtility.choose_full_name(
                            t.person_names, case=None, gender=None
                        )
                    else:
                        d["v"] = t.val
                if t.kind in {
                    TOK.WORD,
                    TOK.ENTITY,
                    TOK.PERSON,
                    TOK.NUMBER,
                    TOK.YEAR,
                    TOK.ORDINAL,
                    TOK.PERCENT,
                }:
                    d["i"] = tags[ix]
                    ix += 1
                if t.kind == TOK.WORD and " " in d["x"]:
                    # Some kind of phrase: split it
                    xlist = d["x"].split()
                    for x in xlist:
                        d["x"] = x
                        if x == "og":
                            # Probably intermediate word: fjármála- og efnahagsráðherra
                            yield TokenDict(x="og", i="c")
                        else:
                            yield d.copy()
                elif t.kind == TOK.PERSON:
                    # Split person tokens into subtokens for each name component
                    xlist = d["x"].split()  # Name as it originally appeared
                    slist = cast(str, d["v"]).split()  # Stem (nominal) form of name
                    # xlist may be shorter than slist, but that is OK
                    for x, s in zip(xlist, slist):
                        d["x"] = x
                        d["v"] = s
                        yield d.copy()
                elif t.kind == TOK.ENTITY:
                    # Split entity tokens into subtokens for each name component
                    xlist = d["x"].split()  # Name as it originally appeared
                    for x in xlist:
                        d["x"] = x
                        yield d.copy()
                # !!! TBD: Tokens such as dates, amounts and currencies
                # !!! should be split here into multiple subtokens
                else:
                    yield d

        return list(gen_tokens())
