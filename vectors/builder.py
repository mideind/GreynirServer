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

import json
import logging
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO)

from settings import Settings
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
            # Fetch bags of words for grouped by articles
            q = session.execute(
                """
                    select article_id, heading, stem, cat, cnt
                        from words
                        join articles on articles.id = words.article_id
                        order by article_id
                    ;
                """
            )
            bag = []
            last_uuid = None
            for uuid, heading, stem, cat, cnt in q:
                if uuid != last_uuid:
                    if bag:
                        # Finishing the last article: yield its bag
                        # print("Yielding bag of {0} words".format(len(bag)))
                        yield xform(bag)
                        bag = []
                    # Beginning a new article with an empty bag
                    last_uuid = uuid
                    # print("{0}".format(heading))
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
    _DICTIONARY_FILE = '/tmp/reynir.dict'
    _PLAIN_CORPUS_FILE = '/tmp/corpus.mm'
    _TFIDF_CORPUS_FILE = '/tmp/corpus-tfidf.mm'
    _TFIDF_MODEL_FILE = '/tmp/tfidf.model'
    _LSI_MODEL_FILE = '/tmp/lsi-{0}.model'
    _LDA_MODEL_FILE = '/tmp/lda-{0}.model'

    def __init__(self, verbose = False):
        self._verbose = verbose
        self._dictionary = None
        self._tfidf = None
        self._model = None
        self._model_name = None

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
            self.load_lda_model()
        if self._verbose:
            print("Calculating topics")
        TOPICS = {
            "Íþróttir":
                """
íþrótt/kvk
mark/hk
skora/so
lið/hk
keppni/kvk
keppa/so
leikur/kk
deild/kvk
úrvalsdeild/kvk
stig/hk
hálfleikur/kk
sigur/kk
umferð/kvk
knattspyrna/kvk
pepsi/entity
mæta/so
mínúta/kvk
sæti/hk
leikmaður/kk
leika/so
bolti/kk
heimsleikur/kk
þraut/kvk
karlaflokkur/kk
kvennaflokkur/kk
grein/kvk
crossfit/entity
einstaklingsflokkur/kk
efri/lo
lokagrein/kvk
keppnisdagur/kk
heimavöllur/kk
fótbolti/kk
handbolti/kk
körfubolti/kk
körfuknattleikur/kk
mót/hk
evrópumót/hk
heimsmeistaramót/hk
reykjavíkurmót/hk
árangur/kk
verðlaun/hk
viðureign/kvk
undanúrslit/hk
úrslit/hk
bikarúrslit/hk
leikbann/hk
rauður/lo
spjald/hk
varnarmaður/kk
keppnistímabil/hk
leikmannahópur/kk
landsliðsmaður/kk
englandsmeistari/kk
íslandsmeistari/kk
evrópumeistari/kk
heimsmeistari/kk
beinn/lo
lýsing/kvk
keppandi/kk
sundkona/kvk
bringusund/hk
skriðsund/hk
flugsund/hk
baksund/hk
íþróttaviðburður/kk
fyrirliði/kk
gullverðlaun/hk
heimsmet/hk
dauðafæri/hk
                """,
            "Viðskipti":
                """
fyrirtæki/hk
sprotafyrirtæki/hk
kaupa/so
selja/so
hlutabréf/hk
skuldabréf/hk
vísitala/kvk
gengi/hk
tilboð/hk
bjóða/so
undirbjóða/so
félag/hk
hlutafélag/hk
móðurfélag/hk
dótturfélag/hk
samvinnufélag/hk
samlagsfélag/hk
samsteypa/kvk
samstæða/kvk
hækkun/kvk
lækkun/kvk
hækka/so
lækka/so
kauphöll/kvk
velta/kvk
hagnaður/kk
viðskipti/hk
fjárfesting/kvk
fjárfesta/so
tap/hk
hagnast/so
tapa/so
afkoma/kvk
hlutabréfamarkaður/kk
banki/kk
bankareikningur/kk
hlaupareikningur/kk
rekstur/kk
sala/kvk
eign/kvk
skuld/kvk
veltufé/hk
peningur/kk
mynt/kvk
króna/kvk
fjármunir/kk
afkoma/kvk
hlutafélagaskrá/kvk
verð/hk
markaðsverð/hk
samningsverð/hk
útboðsverð/hk
eignarhald/hk
arður/kk
arðgreiðsla/kvk
ávöxtun/kvk
ávöxtunarkrafa/kvk
kaupréttur/kk
valréttur/kk
samningur/kk
kaupsamningur/kk
samruni/kk
söluferli/hk
gjaldþrot/hk
framkvæmdastjóri/kk
framkvæmdastýra/kvk
forstjóri/kk
fjármálastjóri/kk
stjórnandi/kk
innherji/kk
innherjaviðskipti/hk
sjóður/kk
fjárfestingarsjóður/kk
verðbréfasjóður/kk
sprotasjóður/kk
lánasjóður/kk
eftirspurn/kvk
                """,
            "Stjórnmál":
                """
flokkur/kk
þingflokkur/kk
ríkisstjórn/kvk
alþingi/hk
þing/hk
stjórnmál/hk
frumvarp/hk
stjórnarfrumvarp/hk
umsögn/kvk
frambjóðandi/kk
forsetaframbjóðandi/kk
framboð/hk
þingframboð/hk
forsetaframboð/hk
þingmaður/kk
þingkona/kvk
alþingismaður/kk
alþingiskona/kvk
ráðherra/kk
forsætisráðherra/kk
fjármálaráðherra/kk
innanríkisráðherra/kk
utanríkisráðherra/kk
velferðarráðherra/kk
atvinnuvegaráðherra/kk
umhverfisráðherra/kk
formaður/kk
leiðtogi/kk
atkvæði/hk
greiða/so
kjósa/so
samþykkja/so
hafna/so
umræða/kvk
stjórnarskrá/kvk
atkvæðagreiðsla/kvk
þjóðaratkvæðagreiðsla/kvk
kosning/kvk
kosningastjóri/kk
kosningabarátta/kvk
fylgi/hk
þinglegur/lo
skoðanakönnun/kvk
könnun/kvk
stjórnarandstaða/kvk
þingkosning/kvk
kjörtímabil/hk
fundur/kk
mótmæli/hk
málþóf/hk
málefni/hk
prófkjör/hk
borgarfulltrúi/kk
varaborgarfulltrúi/kk
bæjarfulltrúi/kk
varabæjarfulltrúi/kk
fulltrúaráð/hk
atvinnuveganefnd/kvk
forsætisnefnd/kvk
utanríkismálanefnd/kvk
fjárlaganefnd/kvk
velferðarnefnd/kvk
viðskiptanefnd/kvk
eftirlitsnefnd/kvk
flokksþing/hk
landsfundur/kk
                """
        }
        with SessionContext(commit = True) as session:
            for topic in session.query(Topic).all():
                if self._verbose:
                    print("Topic {0}".format(topic.name))
                if topic.name in TOPICS:
                    # Overwrite the existing keywords
                    keywords = list(set(TOPICS[topic.name].split()))
                    topic.keywords = " ".join(keywords)
                else:
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

    def assign_article_topics(self, article_id, heading):
        """ Assign the appropriate topics to the given article in the database """
        SIMILARITY_THRESHOLD = 0.200
        if self._dictionary is None:
            self.load_dictionary()
        if self._tfidf is None:
            self.load_tfidf_model()
        if self._model is None:
            self.load_lda_model()
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
            if wlist:
                bag = self._dictionary.doc2bow(wlist)
                tfidf = self._tfidf[bag]
                article_lda = self._model[tfidf]
                if self._verbose:
                    print("{0} : {1}".format(article_id, heading))
                #print("Article LDA is {0}".format(article_lda))
                for topic in session.query(Topic).all():
                    topic_lda = json.loads(topic.vector)[self._model_name]
                    similarity = matutils.cossim(article_lda, topic_lda)
                    if self._verbose:
                        print("   Similarity to topic {0} is {1:.3f}".format(topic.name, similarity))
                    if similarity >= SIMILARITY_THRESHOLD:
                        # This is a topic of the article
                        topics.append(topic.id)
            # Topics found (if any): delete previous ones (if any)
            session.execute(ArticleTopic.table().delete().where(ArticleTopic.article_id == article_id))
            # ...and add the new ones
            for topic in topics:
                session.add(ArticleTopic(article_id = article_id, topic_id = topic))


if __name__ == "__main__":

    Settings.read("Vectors.conf")

    rc = ReynirCorpus(verbose = True)
    #rc.create_dictionary()
    #rc.create_plain_corpus()
    #rc.create_tfidf_corpus()
    #rc.create_tfidf_model()
    #rc.create_lda_model(passes = 15)
    #rc.create_lsi_model()
    rc.load_lsi_model()
    rc.calculate_topics()
    with SessionContext(commit = True) as session:
        q = session.query(Article.id, Article.heading).all()
    for article_id, heading in q:
        rc.assign_article_topics(article_id, heading)
