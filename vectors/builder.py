# type: ignore
"""
    Greynir: Natural language processing for Icelandic

    Document index builder & topic tagger module

    Copyright (C) 2021 Miðeind ehf.
    Original author: Vilhjálmur Þorsteinsson

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
    

    This module is written in Python 3

    This module reads articles from the Greynir article database as bags-of-words
    and indexes them using Latent Semantic Indexing (LSI, also called Latent Semantic
    Analysis, LSA), with indexes generated with the help of the Gensim document
    processing module.

    The indexing proceeds in stages (cf. https://radimrehurek.com/gensim/tut2.html):

    1) Conversion of article contents (taken from the words database table)
        into a corpus stream, yielding each article as a bag-of-words
        via the CorpusIterator class. Note that the words database table has
        already been filtered so that it only contains significant verbs,
        nouns, adjectives and person and entity names - all normalized
        (i.e. verbs to 'nafnháttur', nouns to nominative singular, and
        adjectives to normal nominative singular masculine).

    2) Generation of a Gensim dictionary (vocabulary) across the corpus stream,
        cutting out rare words, resulting in a word count vector

    3) Calculation of word weights from the dictionary via the TFIDF algorithm,
        generating a TFIDF vector (TFIDF=term frequency–inverse document frequency,
        cf. http://www.tfidf.com/)

    4) Generation of the LSI lower-dimensionality model (matrix) from the corpus
        after transformation of each document through the TFIDF vector

    After the LSI model has been generated, it can be used to calculate LSI
    vectors for any set of words. We calculate such vectors for each topic
    in the topics database table by using the topic keywords as input for each
    LSI vector. Subsequently, the closeness of any article to a topic can be
    estimated by calculating the cosine similarity between the article's LSI
    vector and the topic's LSI vector.

"""

import sys
import getopt
import json
import time
from datetime import datetime
from collections import defaultdict

from settings import Settings, Topics, NoIndexWords
from db import SessionContext
from db.models import Article, Topic, ArticleTopic, Word
from db.queries import TermTopicsQuery
from similar import SimilarityClient

import numpy as np
from gensim import corpora, models, matutils


def w_from_stem(stem, cat):
    """ Convert a (stem, cat) tuple to a bag-of-words key """
    return stem.lower().replace("-", "").replace(" ", "_") + "/" + cat


class CorpusIterator:

    """ Iterate through the Greynir words database, yielding a bag-of-words
        for each article """

    def __init__(self, dictionary=None):
        self._dictionary = dictionary

    def __iter__(self):
        """ Iterate through articles (documents) """
        print("Starting iteration through corpus from words table")
        if self._dictionary is not None:
            xform = lambda x: self._dictionary.doc2bow(x)
        else:
            xform = lambda x: x
        with SessionContext(commit=True) as session:
            # Fetch bags of words sorted by articles
            q = (
                session.query(Word.article_id, Word.stem, Word.cat, Word.cnt)
                .order_by(Word.article_id)
                .yield_per(2000)
            )
            bag = []
            last_uuid = None
            for uuid, stem, cat, cnt in q:
                if uuid != last_uuid:
                    if bag:
                        # Finishing the last article: yield its bag
                        # print("Yielding bag of {0} words".format(len(bag)))
                        yield xform(bag)
                        bag = []
                    # Beginning a new article with an empty bag
                    last_uuid = uuid
                # Convert stem to lowercase and replace spaces with underscores
                w = w_from_stem(stem, cat)
                if cnt == 1:
                    bag.append(w)
                else:
                    bag.extend([w] * cnt)
            if (last_uuid is not None) and bag:
                # print("Yielding bag of {0} words".format(len(bag)))
                yield xform(bag)
        print("Finished iteration through corpus from words table")


class ReynirDictionary(corpora.Dictionary):

    """ Subclass of gensim.corpora.Dictionary that adds a __contains__
        operator for easy membership check """

    def __init__(self, iterator):
        super().__init__(iterator)

    def __contains__(self, word):
        return word in self.token2id


class ReynirCorpus:

    """ Wraps the document indexing functionality """

    # Default number of dimensions in topic vectors
    _DEFAULT_DIMENSIONS = 200

    # Work file names
    _DICTIONARY_FILE = "./models/reynir.dict"
    _PLAIN_CORPUS_FILE = "./models/corpus.mm"
    _TFIDF_CORPUS_FILE = "./models/corpus-tfidf.mm"
    _TFIDF_MODEL_FILE = "./models/tfidf.model"
    _LSI_MODEL_FILE = "./models/lsi-{0}.model"
    _LDA_MODEL_FILE = "./models/lda-{0}.model"

    def __init__(self, verbose=False, dimensions=None):
        self._verbose = verbose
        self._dictionary = None
        self._tfidf = None
        self._model = None
        self._model_name = None
        self._topics = None
        self._dimensions = dimensions or ReynirCorpus._DEFAULT_DIMENSIONS

    @property
    def dimensions(self):
        return self._dimensions

    def create_dictionary(self):
        """ Iterate through the article database
            and create a fresh Gensim dictionary """
        ci = CorpusIterator()
        dic = ReynirDictionary(ci)
        # Drop words that only occur only once or twice in the entire set
        dic.filter_extremes(no_below=3, keep_n=None)
        dic.save(self._DICTIONARY_FILE)
        self._dictionary = dic

    def load_dictionary(self):
        """ Load a dictionary from a previously prepared file """
        self._dictionary = ReynirDictionary.load(self._DICTIONARY_FILE)

    def create_plain_corpus(self):
        """ Create a plain vector corpus, where each vector represents a
            document. Each element of the vector contains the count of
            the corresponding word (as indexed by the dictionary) in
            the document. """
        if self._dictionary is None:
            self.load_dictionary()
        dci = CorpusIterator(dictionary=self._dictionary)
        corpora.MmCorpus.serialize(self._PLAIN_CORPUS_FILE, dci)

    def load_plain_corpus(self):
        """ Load the plain corpus from file """
        return corpora.MmCorpus(self._PLAIN_CORPUS_FILE)

    def create_tfidf_model(self):
        """ Create a fresh TFIDF model from a dictionary """
        if self._dictionary is None:
            self.load_dictionary()
        tfidf = models.TfidfModel(dictionary=self._dictionary)
        tfidf.save(self._TFIDF_MODEL_FILE)
        self._tfidf = tfidf

    def load_tfidf_model(self):
        """ Load an already generated TFIDF model """
        self._tfidf = models.TfidfModel.load(self._TFIDF_MODEL_FILE, mmap="r")

    def create_tfidf_corpus(self):
        """ Create a TFIDF corpus from a plain vector corpus """
        if self._tfidf is None:
            self.load_tfidf_model()
        corpus = self.load_plain_corpus()
        corpus_tfidf = self._tfidf[corpus]
        corpora.MmCorpus.serialize(self._TFIDF_CORPUS_FILE, corpus_tfidf)

    def load_tfidf_corpus(self):
        """ Load a TFIDF corpus from file """
        return corpora.MmCorpus(self._TFIDF_CORPUS_FILE)

    def create_lsi_model(self, **kwargs):
        """ Create an LSI model from the entire words database table """
        corpus_tfidf = self.load_tfidf_corpus()
        if self._dictionary is None:
            self.load_dictionary()
        # Initialize an LSI transformation
        lsi = models.LsiModel(
            corpus_tfidf,
            id2word=self._dictionary,
            num_topics=self._dimensions,
            **kwargs
        )
        # if self._verbose:
        #    lsi.print_topics(num_topics = self._dimensions)
        # Save the generated model
        lsi.save(self._LSI_MODEL_FILE.format(self._dimensions))

    def load_lsi_model(self):
        """ Load a previously generated LSI model """
        self._model = models.LsiModel.load(
            self._LSI_MODEL_FILE.format(self._dimensions), mmap="r"
        )
        self._model_name = "lsi"

    def create_lda_model(self, **kwargs):
        """ Create a Latent Dirichlet Allocation (LDA) model from the
            entire words database table """
        corpus_tfidf = self.load_tfidf_corpus()
        if self._dictionary is None:
            self.load_dictionary()
        # Initialize an LDA transformation
        lda = models.LdaMulticore(
            corpus_tfidf,
            id2word=self._dictionary,
            num_topics=self._dimensions,
            **kwargs
        )
        if self._verbose:
            lda.print_topics(num_topics=self._dimensions)
        # Save the generated model
        lda.save(self._LDA_MODEL_FILE.format(self._dimensions))

    def load_lda_model(self):
        """ Load a previously generated LDA model """
        self._model = models.LdaMulticore.load(
            self._LDA_MODEL_FILE.format(self._dimensions), mmap="r"
        )
        self._model_name = "lda"

    def calculate_topics(self):
        """ Recalculate the topic vectors in the topics database table """
        if self._dictionary is None:
            self.load_dictionary()
        if self._tfidf is None:
            self.load_tfidf_model()
        if self._model is None:
            self.load_lsi_model()
        if self._verbose:
            print("Calculating topics")
        with SessionContext(commit=True) as session:
            for topic in session.query(Topic).all():
                if self._verbose:
                    print("Topic {0}".format(topic.name))
                if topic.name in Topics.DICT:
                    # Overwrite the existing keywords
                    keywords = list(Topics.DICT[topic.name])  # Convert set to list
                    topic.keywords = " ".join(keywords)
                    # Set the identifier
                    topic.identifier = Topics.ID[topic.name]
                    # Set the threshold
                    topic.threshold = Topics.THRESHOLD[topic.name]
                else:
                    # Use the ones that are already there
                    keywords = topic.keywords.split()
                assert all("/" in kw for kw in keywords)  # Must contain a slash
                if self._verbose:
                    print("Keyword list: {0}".format(keywords))
                bag = self._dictionary.doc2bow(keywords)
                tfidf = self._tfidf[bag]
                vec = self._model[tfidf]
                if self._verbose:
                    if self._model_name == "lda":
                        print("LDA: {0}".format(vec))
                        for t, _ in vec:
                            print("Topic #{0}".format(t))
                            wt = self._model.get_topic_terms(t, topn=25)
                            for word, wprob in wt:
                                print(
                                    "   {0} has probability {1:.3f}".format(
                                        self._dictionary.get(word), wprob
                                    )
                                )
                    elif self._model_name == "lsi":
                        pass
                        # self._model.print_debug(num_topics = 20)
                # Update the vector field, setting it to a JSON vector value
                d = {}
                d[self._model_name] = [(int(ix), float(f)) for ix, f in vec]
                topic.vector = json.dumps(d)

    def load_topics(self):
        """ Load the topics into a dict of topic vectors by topic id """
        self._topics = {}
        with SessionContext(commit=True) as session:
            for topic in session.query(Topic).all():
                if topic.vector:
                    topic_vector = json.loads(topic.vector)[self._model_name]
                    if topic_vector:
                        self._topics[topic.id] = dict(
                            name=topic.name,
                            vector=topic_vector,
                            threshold=topic.threshold,
                        )

    def get_topic_vector(self, terms):
        """ Calculate a topic vector corresponding to the given list
            of search terms, which are assumed to have the form (stem, category).
            Return the topic vector as well as a list of weights of
            each search term """
        if self._dictionary is None:
            self.load_dictionary()
        if self._tfidf is None:
            self.load_tfidf_model()
        if self._model is None:
            self.load_lsi_model()
        # Convert the word list, assumed to contain items of the form 'stem/cat',
        # to a bag of word indexes
        wlist = [w_from_stem(stem, cat) for stem, cat in terms]
        bag = self._dictionary.doc2bow(wlist)
        print("Search terms:\n   {0}".format(terms))
        if bag:
            # We have some terms in the bag (i.e. they were in the dictionary)
            # Apply the term frequency - inverse document frequency transform
            tfidf = self._tfidf[bag]
            # Map the resulting vector to the LSI model space
            topic_vector = np.array([float(x) for _, x in self._model[tfidf]])
        else:
            # No bag, we're just going to use word occurrences
            topic_vector = np.zeros(self._dimensions)
        # For words that we want to look up from the words table, calculate a
        # weighted average of the topic vectors of documents where those
        # words appear
        missing = np.zeros(self._dimensions)
        weight_missing = 0.0
        lb = len(bag)
        term_weights = []

        # We have missing words: look'em up
        with SessionContext(commit=True, read_only=True) as session:
            # The same (stem, cat) tuple may appear multiple times:
            # coalesce into one counting dictionary

            for index, (stem, cat) in enumerate(terms):

                def word_lookup_weight(stem, cat):
                    """ Does this term call for a lookup in the words database table? """
                    if cat == "entity" or cat.startswith("person"):
                        # We look up all entity and person names
                        # and give them extra weight
                        return 2.0
                    if cat in {"kk", "kvk", "hk"} and stem[0].isupper() and index > 0:
                        # Noun starting with a capital letter, not the first word in a sentence:
                        # assume it's a proper name and do a lookup with a weight of 1.6
                        return 1.6
                    w = w_from_stem(stem, cat)
                    if isinstance(self._dictionary, ReynirDictionary):
                        in_dict = w in self._dictionary
                    else:
                        # !!! TODO: This else-branch can be removed once a new
                        # !!! ReynirDictionary has been built and pickled
                        in_dict = w in self._dictionary.token2id
                    # Without further reason, we don't look up terms that already
                    # exist in the LSI model dictionary. For other terms, they
                    # appear to be rare and we give them a slight overweight if
                    # they are found in the words table.
                    return 0.0 if in_dict else 1.2

                weight = word_lookup_weight(stem, cat)

                if weight == 0.0:
                    # If weight is 0.0, we don't need to bother
                    # (This means that the word is in the LSI model dictionary
                    # and not special in any way. From the overall search term
                    # point of view, we give it a weight of 1.0)
                    term_weights.append(1.0)
                    continue

                if (
                    cat in NoIndexWords.CATEGORIES_TO_INDEX
                    and (stem, cat) not in NoIndexWords.SET
                ):
                    # We have a significant (potentially indexable)
                    # person, entity, noun, adjective or verb. Give it
                    # a weight in the final topic vector.

                    def clean(stem):
                        """ Eliminate composite word hyphens from the stem """
                        if "- og " in stem or "- eða " in stem:
                            # Leave 'iðnaðar- og viðskiptaráðuneyti' alone
                            return stem
                        # We want to keep other types of hyphens (surrounded by spaces)
                        # such as 'Vestur - Íslendingar'
                        a = stem.split(" - ")
                        return " - ".join(p.replace("-", "") for p in a)

                    clean_stem = clean(stem)
                    q = TermTopicsQuery().execute(
                        session, stem=clean_stem, cat=cat, limit=25
                    )
                    term_vector = np.zeros(self._dimensions)
                    total_cnt = 0
                    # Sum up the topic vectors of the documents where the term
                    # appears, weighted by the number of times it appears
                    # print("Found stem/cat '{0}'/{1} in {2} documents via words table".format(clean_stem, cat, len(q)))
                    for tv_json, cnt in q:
                        # Get the term vector of a single document where the term appears
                        if tv_json and cnt:
                            tv = np.array(json.loads(tv_json))
                            # Multiply the vector by the number of times the term appears
                            total_cnt += cnt
                            term_vector += tv * cnt
                    # Add the combined (weighted average) topic vector of the
                    # term to the 'missing' topic vector
                    if total_cnt > 0:
                        missing += (term_vector / total_cnt) * weight
                        # Keep track of how many 'missing' terms have contributed
                        # to the missing term vector
                        weight_missing += weight
                        term_weights.append(weight)
                    else:
                        # Not found in the words table: this term contributes nothing
                        term_weights.append(0.0)
                else:
                    # print("Discarding term {0} (weight {1:.1f})".format(w_from_stem(stem, cat), weight))
                    term_weights.append(0.0)

        assert len(terms) == len(term_weights)

        if weight_missing > 0.0:
            # Adjust the weight of the returned topic vector so that the missing
            # terms have a contribution that corresponds to their number
            p_tv = lb / (lb + weight_missing)
            # Calculate the relative contribution of the missing terms
            p_m = 1.0 - p_tv
            # Amalgamate the resulting topic vector
            topic_vector = topic_vector * p_tv + missing * p_m

        return topic_vector, term_weights

    def assign_article_topics(self, article_id, heading, process_all=False):
        """ Assign the appropriate topics to the given article in the database """
        if self._dictionary is None:
            self.load_dictionary()
        if self._tfidf is None:
            self.load_tfidf_model()
        if self._model is None:
            self.load_lsi_model()
        if self._topics is None:
            self.load_topics()
        with SessionContext(commit=True) as session:
            q = (
                session.query(Word.stem, Word.cat, Word.cnt)
                .filter(Word.article_id == article_id)
                .all()
            )
            wlist = []
            for stem, cat, cnt in q:
                # Convert stem to lowercase and replace spaces with underscores
                w = w_from_stem(stem, cat)
                if cnt == 1:
                    wlist.append(w)
                else:
                    wlist.extend([w] * cnt)
            topics = []
            article_vector = []
            if self._topics and wlist:
                bag = self._dictionary.doc2bow(wlist)
                tfidf = self._tfidf[bag]
                article_vector = self._model[tfidf]
                topic_names = []
                if self._verbose:
                    print("{0} : {1}".format(article_id, heading))
                for topic_id, topic_info in self._topics.items():
                    topic_name = topic_info["name"]
                    topic_vector = topic_info["vector"]
                    topic_threshold = topic_info["threshold"]
                    # Calculate the cosine similarity between the article and the topic
                    similarity = matutils.cossim(article_vector, topic_vector)
                    if self._verbose:
                        print(
                            "   Similarity to topic {0} is {1:.3f}".format(
                                topic_name, similarity
                            )
                        )
                    if similarity >= topic_threshold:
                        # Similar enough: this is a topic of the article
                        topics.append(topic_id)
                        topic_names.append((topic_name, similarity))
                if topic_names and not process_all:
                    print("Article '{0}':\n   topics {1}".format(heading, topic_names))
            # Topics found (if any): delete previous ones (if any)
            session.execute(
                ArticleTopic.table()
                .delete()
                .where(ArticleTopic.article_id == article_id)
            )
            # ...and add the new ones
            for topic_id in topics:
                session.add(ArticleTopic(article_id=article_id, topic_id=topic_id))
            # Update the indexed timestamp and the article topic vector
            a = session.query(Article).filter(Article.id == article_id).one_or_none()
            if a is not None:
                a.indexed = datetime.utcnow()
                if article_vector:
                    # Store a pure list of floats
                    topic_vector = [t[1] for t in article_vector]
                    a.topic_vector = json.dumps(topic_vector)
                else:
                    a.topic_vector = None

    def assign_topics(self, limit=None, process_all=False, uuid=None):
        """ Assign topics to all articles that have no such assignment yet """
        with SessionContext(commit=True) as session:
            # Fetch articles that haven't been indexed (or have been parsed since),
            # and that have at least one associated Word in the words table.
            q = session.query(Article.id, Article.heading)
            if uuid:
                q = q.filter(Article.id == uuid)
            elif not process_all:
                q = q.filter(
                    (Article.indexed == None) | (Article.indexed < Article.parsed)
                )
            q = q.join(Word).group_by(Article.id, Article.heading)
            if uuid:
                q = q.all()
            elif limit is None:
                q = q.yield_per(2000)
            else:
                q = q[0:limit]
        for article_id, heading in q:
            self.assign_article_topics(article_id, heading, process_all=process_all)


def build_model(verbose=False):
    """ Build a new model from the words (and articles) table """

    print("------ Greynir starting model build -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}".format(ts))

    t0 = time.time()

    rc = ReynirCorpus(verbose=verbose)
    print("Creating dictionary")
    rc.create_dictionary()
    print("Creating plain corpus")
    rc.create_plain_corpus()
    print("Creating TF-IDF model")
    rc.create_tfidf_model()
    print("Creating TF-IDF corpus")
    rc.create_tfidf_corpus()
    # rc.create_lda_model(passes = 15)
    print("Creating LSI model")
    rc.create_lsi_model()

    t1 = time.time()

    print("\n------ Model build completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


def calculate_topics(verbose=False):
    """ Recalculate topic vectors from keywords """

    print("------ Greynir recalculating topic vectors -------")
    rc = ReynirCorpus(verbose=verbose)
    rc.load_lsi_model()
    rc.calculate_topics()
    print("------ Greynir recalculation complete -------")


def tag_articles(limit, verbose=False, process_all=False, uuid=None):
    """ Tag all untagged articles or articles that
        have been parsed since they were tagged """

    print("------ Greynir starting tagging -------")
    if uuid:
        print("Tagging article {0}".format(uuid))
    elif process_all:
        print("Processing all articles")
    elif limit:
        print("Limit: {0} articles".format(limit))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}".format(ts))

    t0 = time.time()

    rc = ReynirCorpus(verbose=verbose)
    rc.load_lsi_model()
    rc.assign_topics(limit, process_all, uuid)

    t1 = time.time()

    print("\n------ Tagging completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


def notify_similarity_server():
    """ Notify the similarity server - if running - that article tags have been updated """
    try:
        client = SimilarityClient()
        client.refresh_topics()
        client.close()
    except Exception as e:
        print("Exception in notify_similarity_server(): {0}".format(e))


class Usage(Exception):
    def __init__(self, msg):
        self.msg = msg


__doc__ = """

    Greynir - Natural language processing for Icelandic

    Index builder and tagger module

    Usage:
        python builder.py [options] command [arguments]

    Options:
        -h, --help       : Show this help text
        -l N, --limit=N  : Limit processing to N articles
        -a, --all        : Process all articles
        -v, --verbose    : Show diagnostics while processing

    Commands:
        tag [uuid] : tag any untagged articles (or the article with the given uuid)
        topics     : recalculate topic vectors from keywords
        model      : rebuild dictionary and model from parsed articles

"""


def _main(argv=None):

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(
                argv[1:], "hl:van", ["help", "limit=", "verbose", "all", "notify"]
            )
        except getopt.error as msg:
            raise Usage(msg)

        limit_specified = False
        limit = 10
        verbose = False
        process_all = False
        notify = False

        # Process options
        for o, a in opts:
            if o in ("-h", "--help"):
                print(__doc__)
                return 0
            elif o in ("-l", "--limit"):
                # Maximum number of articles to parse
                try:
                    limit = int(a)
                    limit_specified = True
                except ValueError:
                    pass
            elif o in ("-v", "--verbose"):
                verbose = True
            elif o in ("-a", "--all"):
                process_all = True
            elif o in ("-n", "--notify"):
                notify = True

        # if process_all and limit_specified:
        #    raise Usage("--all and --limit cannot be used together")

        Settings.read("Vectors.conf")

        # Process arguments
        if not args:
            raise Usage("No command specified")

        la = len(args)
        arg = args[0]
        if arg == "tag":
            # Tag articles
            uuid = args[1] if la > 1 else None
            if la > (1 if uuid is None else 2):
                raise Usage("Too many arguments")
            if uuid:
                if process_all:
                    raise Usage("Conflict between uuid argument and --all option")
                if limit_specified:
                    raise Usage("Conflict between uuid argument and --limit option")
            if process_all and not limit_specified:
                limit = None
            tag_articles(
                limit=limit, verbose=verbose, process_all=process_all, uuid=uuid
            )
            if notify:
                # Inform the similarity server that we have new article tags
                notify_similarity_server()
        elif arg == "topics":
            # Calculate topics
            if la > 1:
                raise Usage("Too many arguments")
            calculate_topics(verbose=verbose)
        elif arg == "model":
            # Rebuild model
            if la > 1:
                raise Usage("Too many arguments")
            build_model(verbose=verbose)
        else:
            raise Usage("Unknown command: '{0}'".format(arg))

    except Usage as err:
        print(err.msg, file=sys.stderr)
        print("For help use --help", file=sys.stderr)
        return 2

    # Completed with no error
    return 0


if __name__ == "__main__":

    sys.exit(_main())
