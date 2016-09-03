"""
    Reynir: Natural language processing for Icelandic

    Document index builder module

    Copyright (c) 2016 Vilhjalmur Thorsteinsson
    All rights reserved
    See the accompanying README.md file for further licensing and copyright information.

    This module is written in Python 3

    This module reads articles from the Reynir article database as bags-of-words
    and indexes them with latent semantic indexes generated with the help of
    the Gensim document processing module.

"""

import sys
import getopt
import json
import time
from datetime import datetime
#import logging
#logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

from settings import Settings, Topics
from scraperdb import Article, Topic, ArticleTopic, Word, SessionContext

from gensim import corpora, models, matutils


class CorpusIterator:

    def __init__(self, dictionary = None):
        self._dictionary = dictionary

    def __iter__(self):
        """ Iterate through articles (documents) """
        print("Starting iteration through corpus from words table")
        if self._dictionary is not None:
            xform = lambda x: self._dictionary.doc2bow(x)
        else:
            xform = lambda x: x
        with SessionContext(commit = True) as session:
            # Fetch bags of words sorted by articles
            q = session.execute(
                """
                    select article_id, stem, cat, cnt
                        from words
                        order by article_id
                    ;
                """
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
                w = stem.lower().replace(" ", "_") + "/" + cat
                if cnt == 1:
                    bag.append(w)
                else:
                    bag.extend([w] * cnt)
            if last_uuid is not None:
                # print("Yielding bag of {0} words".format(len(bag)))
                yield xform(bag)


class ReynirCorpus:

    # Work file names
    _DICTIONARY_FILE = './models/reynir.dict'
    _PLAIN_CORPUS_FILE = './models/corpus.mm'
    _TFIDF_CORPUS_FILE = './models/corpus-tfidf.mm'
    _TFIDF_MODEL_FILE = './models/tfidf.model'
    _LSI_MODEL_FILE = './models/lsi-{0}.model'
    _LDA_MODEL_FILE = './models/lda-{0}.model'

    def __init__(self, verbose = False):
        self._verbose = verbose
        self._dictionary = None
        self._tfidf = None
        self._model = None
        self._model_name = None
        self._topics = None

    def create_dictionary(self):
        """ Iterate through the article database
            and create a fresh Gensim dictionary """
        ci = CorpusIterator()
        dic = corpora.Dictionary(ci)
        if self._verbose:
            print("Dictionary before filtering:")
            print(dic)
        # Drop words that only occur only once or twice in the entire set
        dic.filter_extremes(no_below=3, keep_n=None)
        if self._verbose:
            print("Dictionary after filtering:")
            print(dic)
        dic.save(self._DICTIONARY_FILE)
        self._dictionary = dic

    def load_dictionary(self):
        """ Load a dictionary from a previously prepared file """
        self._dictionary = corpora.Dictionary.load(self._DICTIONARY_FILE)

    def create_plain_corpus(self):
        """ Create a plain vector corpus, where each vector represents a
            document. Each element of the vector contains the count of
            the corresponding word (as indexed by the dictionary) in
            the document. """
        if self._dictionary is None:
            self.load_dictionary()
        dci = CorpusIterator(dictionary = self._dictionary)
        corpora.MmCorpus.serialize(self._PLAIN_CORPUS_FILE, dci)

    def load_plain_corpus(self):
        """ Load the plain corpus from file """
        return corpora.MmCorpus(self._PLAIN_CORPUS_FILE)

    def create_tfidf_model(self):
        """ Create a fresh TFIDF model from a dictionary """
        if self._dictionary is None:
            self.load_dictionary()
        tfidf = models.TfidfModel(dictionary = self._dictionary)
        tfidf.save(self._TFIDF_MODEL_FILE)
        self._tfidf = tfidf

    def load_tfidf_model(self):
        """ Load an already generated TFIDF model """
        self._tfidf = models.TfidfModel.load(self._TFIDF_MODEL_FILE, mmap='r')

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

    def create_lsi_model(self, num_topics = 200, **kwargs):
        """ Create an LSI model from the entire words database table """
        corpus_tfidf = self.load_tfidf_corpus()
        if self._dictionary is None:
            self.load_dictionary()
        # Initialize an LSI transformation
        lsi = models.LsiModel(corpus_tfidf, id2word=self._dictionary,
            num_topics=num_topics, **kwargs)
        if self._verbose:
            lsi.print_topics(num_topics = num_topics)
        # Save the generated model
        lsi.save(self._LSI_MODEL_FILE.format(num_topics))

    def load_lsi_model(self, num_topics = 200):
        """ Load a previously generated LSI model """
        self._model = models.LsiModel.load(self._LSI_MODEL_FILE.format(num_topics), mmap='r')
        self._model_name = "lsi"

    def create_lda_model(self, num_topics = 200, **kwargs):
        """ Create a Latent Dirichlet Allocation (LDA) model from the
            entire words database table """
        corpus_tfidf = self.load_tfidf_corpus()
        if self._dictionary is None:
            self.load_dictionary()
        # Initialize an LDA transformation
        lda = models.LdaMulticore(corpus_tfidf, id2word=self._dictionary,
            num_topics=num_topics, **kwargs)
        if self._verbose:
            lda.print_topics(num_topics = num_topics)
        # Save the generated model
        lda.save(self._LDA_MODEL_FILE.format(num_topics))

    def load_lda_model(self, num_topics = 200):
        """ Load a previously generated LDA model """
        self._model = models.LdaMulticore.load(self._LDA_MODEL_FILE.format(num_topics), mmap='r')
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
        with SessionContext(commit = True) as session:
            for topic in session.query(Topic).all():
                if self._verbose:
                    print("Topic {0}".format(topic.name))
                if topic.name in Topics.DICT:
                    # Overwrite the existing keywords
                    keywords = list(Topics.DICT[topic.name]) # Convert set to list
                    topic.keywords = " ".join(keywords)
                else:
                    # Use the ones that are already there
                    keywords = topic.keywords.split()
                assert all('/' in kw for kw in keywords) # Must contain a slash
                if self._verbose:
                    print("Keyword list: {0}".format(keywords))
                bag = self._dictionary.doc2bow(keywords)
                #if self._verbose:
                #    print("Bag: {0}".format(bag))
                tfidf = self._tfidf[bag]
                #if self._verbose:
                #    print("Tfidf: {0}".format(tfidf))
                vec = self._model[tfidf]
                if self._verbose:
                    if self._model_name == "lda":
                        print("LDA: {0}".format(vec))
                        for t, prob in vec:
                            print("Topic #{0}".format(t))
                            wt = self._model.get_topic_terms(t, topn=25)
                            for word, wprob in wt:
                                print("   {0} has probability {1:.3f}".format(self._dictionary.get(word), wprob))
                    elif self._model_name == "lsi":
                        pass
                        # self._model.print_debug(num_topics = 20)
                # Update the vector field, setting it to a JSON vector value
                d = {}
                d[self._model_name] = [(int(ix), float(f)) for ix, f in vec]
                topic.vector = json.dumps(d)

    def load_topics(self):
        """ Load the topics into a dict of topic vectors by topic id """
        self._topics = { }
        with SessionContext(commit = True) as session:
            for topic in session.query(Topic).all():
                if topic.vector:
                    topic_vector = json.loads(topic.vector)[self._model_name]
                    if topic_vector:
                        self._topics[topic.id] = dict(name = topic.name,
                            vector = topic_vector, threshold = topic.threshold)

    def assign_article_topics(self, article_id, heading):
        """ Assign the appropriate topics to the given article in the database """
        if self._dictionary is None:
            self.load_dictionary()
        if self._tfidf is None:
            self.load_tfidf_model()
        if self._model is None:
            self.load_lda_model()
        if self._topics is None:
            self.load_topics()
        with SessionContext(commit = True) as session:
            q = session.query(Word.stem, Word.cat, Word.cnt).filter(Word.article_id == article_id).all()
            wlist = []
            for stem, cat, cnt in q:
                # Convert stem to lowercase and replace spaces with underscores
                w = stem.lower().replace(" ", "_") + "/" + cat
                if cnt == 1:
                    wlist.append(w)
                else:
                    wlist.extend([w] * cnt)
            topics = []
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
                    # Calculate the cosine similarity betwee the article and the topic
                    similarity = matutils.cossim(article_vector, topic_vector)
                    if self._verbose:
                        print("   Similarity to topic {0} is {1:.3f}".format(topic_name, similarity))
                    if similarity >= topic_threshold:
                        # Similar enough: this is a topic of the article
                        topics.append(topic_id)
                        topic_names.append((topic_name, similarity))
                if topic_names:
                    print("Article '{0}': topics {1}".format(heading, topic_names))
            # Topics found (if any): delete previous ones (if any)
            session.execute(ArticleTopic.table().delete().where(ArticleTopic.article_id == article_id))
            # ...and add the new ones
            for topic_id in topics:
                session.add(ArticleTopic(article_id = article_id, topic_id = topic_id))
            # Update the indexed timestamp
            a = session.query(Article).filter(Article.id == article_id).one_or_none()
            if a:
                a.indexed = datetime.utcnow()

    def assign_topics(self, limit = None, process_all = False):
        """ Assign topics to all articles that have no such assignment yet """
        with SessionContext(commit = True) as session:
            # Fetch articles that haven't been indexed (or have been parsed since),
            # and that have at least one associated Word in the words table.
            q = session.query(Article.id, Article.heading)
            if not process_all:
                q = q.filter((Article.indexed == None) | (Article.indexed < Article.parsed))
            q = q.join(Word).group_by(Article.id, Article.heading)
            if process_all or limit is None:
                q = q.all()
            else:
                q = q[0:limit]
        for article_id, heading in q:
            self.assign_article_topics(article_id, heading)


def build_model(verbose = False):
    """ Build a new model from the words (and articles) table """

    print("------ Reynir starting model build -------")
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}".format(ts))

    t0 = time.time()

    rc = ReynirCorpus(verbose = verbose)
    rc.create_dictionary()
    rc.create_plain_corpus()
    rc.create_tfidf_model()
    rc.create_tfidf_corpus()
    #rc.create_lda_model(passes = 15)
    rc.create_lsi_model()

    t1 = time.time()

    print("\n------ Model build completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


def calculate_topics(verbose = False):
    """ Recalculate topic vectors from keywords """

    print("------ Reynir recalculating topic vectors -------")
    rc = ReynirCorpus(verbose = verbose)
    rc.load_lsi_model()
    rc.calculate_topics()
    print("------ Reynir recalculation complete -------")


def tag_articles(limit, verbose = False, process_all = False):
    """ Tag all untagged articles or articles that
        have been parsed since they were tagged """

    print("------ Reynir starting tagging -------")
    if limit:
        print("Limit: {0} articles".format(limit))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}".format(ts))

    t0 = time.time()

    rc = ReynirCorpus(verbose = verbose)
    rc.load_lsi_model()
    rc.assign_topics(limit, process_all)

    t1 = time.time()

    print("\n------ Tagging completed -------")
    print("Total time: {0:.2f} seconds".format(t1 - t0))
    ts = "{0}".format(datetime.utcnow())[0:19]
    print("Time: {0}\n".format(ts))


class Usage(Exception):

    def __init__(self, msg):
        self.msg = msg


__doc__ = """

    Reynir - Natural language processing for Icelandic

    Index builder and tagger module

    Usage:
        python builder.py [options] command

    Options:
        -h, --help: Show this help text
        -l N, --limit=N: Limit processing to N articles

    Commands:
        tag     : tag any untagged articles
        topics  : recalculate topic vectors from keywords
        model   : rebuild dictionary and model from parsed articles

"""


def _main(argv = None):

    if argv is None:
        argv = sys.argv
    try:
        try:
            opts, args = getopt.getopt(argv[1:], "hl:va",
                ["help", "limit=", "verbose", "all"])
        except getopt.error as msg:
             raise Usage(msg)

        limit_specified = False
        limit = 10
        verbose = False
        process_all = False

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
                except ValueError as e:
                    pass
            elif o in ("-v", "--verbose"):
                verbose = True
            elif o in ("-a", "--all"):
                process_all = True

        if process_all and limit_specified:
            raise Usage("--all and --limit cannot be used together")

        Settings.read("Vectors.conf")

        # Process arguments
        for arg in args:
            if arg == "tag":
                # Tag articles
                tag_articles(limit = limit, verbose = verbose, process_all = process_all)
                break
            elif arg == "topics":
                # Calculate topics
                calculate_topics(verbose = verbose)
                break
            elif arg == "model":
                # Rebuild model
                build_model(verbose = verbose)
                break
        else:
            # Nothing matched, no break in loop
            raise Usage("No command specified")

    except Usage as err:
        print(err.msg, file = sys.stderr)
        print("For help use --help", file = sys.stderr)
        return 2

    # Completed with no error
    return 0


if __name__ == "__main__":

    sys.exit(_main())

