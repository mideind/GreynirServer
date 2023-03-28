"""

    Greynir: Natural language processing for Icelandic

    Scraper database models

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


    This module describes the SQLAlchemy models for the scraper database.

"""

from __future__ import annotations

from db import Session
from typing import Any, Optional, cast

from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Sequence,
    Boolean,
    UniqueConstraint,
    Index,
    ForeignKey,
    PrimaryKeyConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.dialects.postgresql import UUID as psql_UUID
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from sqlalchemy.orm.relationships import RelationshipProperty
from sqlalchemy.sql.expression import ColumnElement


# Hacks to get properly typed SQLAlchemy column definitions
def StringColumnRequired(n: Optional[int] = None, **kwargs: Any) -> str:
    return cast(str, Column(String(n), nullable=False, **kwargs))


def StringColumn(n: Optional[int] = None, **kwargs: Any) -> Optional[str]:
    return cast(Optional[str], Column(String(n), **kwargs))


def FloatColumnRequired(**kwargs: Any) -> float:
    return cast(float, Column(Float, nullable=False, **kwargs))


def FloatColumn(**kwargs: Any) -> Optional[float]:
    return cast(Optional[float], Column(Float, **kwargs))


def IntegerColumnRequired(**kwargs: Any) -> int:
    return cast(int, Column(Integer, nullable=False, **kwargs))


def IntegerColumn(**kwargs: Any) -> Optional[int]:
    return cast(Optional[int], Column(Integer, **kwargs))


def BooleanColumn(**kwargs: Any) -> Optional[bool]:
    return cast(Optional[bool], Column(Boolean, **kwargs))


def DateTimeColumn(**kwargs: Any) -> Optional[datetime]:
    return cast(Optional[datetime], Column(DateTime, **kwargs))


class CaseInsensitiveComparator(Comparator):
    """Boilerplate from the PostgreSQL documentation to implement
    a case-insensitive comparator"""

    # See https://docs.sqlalchemy.org/en/13/orm/extensions/hybrid.html

    def __eq__(self, other: object) -> ColumnElement[Boolean]:
        return func.lower(self.__clause_element__()) == func.lower(other)  # type: ignore


# Create the SQLAlchemy ORM Base class
# Base: DeclarativeMeta = declarative_base()  # Pylance/Pyright doesn't like this
Base: Any = declarative_base()

# Add a table() function to the Base class, returning the __table__ member.
# Note that this hack is necessary because SqlAlchemy doesn't readily allow
# intermediate base classes between Base and the concrete table classes.
setattr(Base, "table", classmethod(lambda cls: cls.__table__))


class Root(Base):
    """Represents a scraper root, i.e. a base domain and root URL"""

    __tablename__ = "roots"

    # Primary key
    id = cast(
        int,
        Column(
            Integer,
            Sequence("roots_id_seq"),  # type: ignore  # Don't ask me why
            primary_key=True,
        ),
    )

    # Domain suffix, root URL, human-readable description
    domain = StringColumnRequired()
    url = StringColumnRequired()
    description = StringColumn()

    # Default author
    author = StringColumn()
    # Default authority of this source, 1.0 = most authoritative, 0.0 = least authoritative
    authority = FloatColumn()
    # Finish time of last scrape of this root
    scraped = cast(datetime, Column(DateTime, index=True))
    # Module to use for scraping
    scr_module = StringColumn(80)
    # Class within module to use for scraping
    scr_class = StringColumn(80)
    # Are articles of this root visible on the Greynir web?
    visible = cast(bool, Column(Boolean, default=True))
    # Should articles of this root be scraped automatically?
    scrape = cast(bool, Column(Boolean, default=True))

    # The combination of domain + url must be unique
    __table_args__ = (UniqueConstraint("domain", "url"),)

    def __repr__(self):
        return "Root(domain='{0}', url='{1}', description='{2}')".format(
            self.domain, self.url, self.description
        )


class Article(Base):
    """Represents an article from one of the roots, to be scraped
    or having already been scraped"""

    __tablename__ = "articles"

    # The article URL is the primary key
    url = StringColumnRequired(primary_key=True)

    # UUID
    id = cast(
        str,
        Column(
            psql_UUID(as_uuid=False),
            index=True,
            nullable=False,
            unique=True,
            server_default=text("uuid_generate_v1()"),
        ),
    )

    # Foreign key to a root
    root_id = cast(
        Optional[int],
        Column(
            Integer,
            # We don't delete associated articles if the root is deleted
            ForeignKey("roots.id", onupdate="CASCADE", ondelete="SET NULL"),
        ),
    )

    # Article heading, if known
    heading = StringColumn()
    # Article author, if known
    author = StringColumn()
    # Article time stamp, if known
    timestamp = DateTimeColumn(index=True)

    # Authority of this article, 1.0 = most authoritative, 0.0 = least authoritative
    authority = FloatColumn()
    # Time of the last scrape of this article
    scraped = DateTimeColumn(index=True)
    # Time of the last parse of this article
    parsed = DateTimeColumn(index=True)
    # Time of the last processing of this article
    processed = DateTimeColumn(index=True)
    # Time of the last indexing of this article
    indexed = DateTimeColumn(index=True)
    # Module used for scraping
    scr_module = StringColumn(80)
    # Class within module used for scraping
    scr_class = StringColumn(80)
    # Version of scraper class
    scr_version = StringColumn(16)
    # Version of parser/grammar/config
    parser_version = StringColumn(64)
    # Parse statistics
    num_sentences = IntegerColumn()
    num_parsed = IntegerColumn()
    ambiguity = FloatColumn()

    # The HTML obtained in the last scrape
    html = StringColumn()
    # The parse tree obtained in the last parse
    tree = StringColumn()
    # The tokens of the article in JSON string format
    tokens = StringColumn()
    # The article topic vector as an array of floats in JSON string format
    topic_vector = StringColumn()

    # The back-reference to the Root parent of this Article
    root: RelationshipProperty[Root] = relationship(
        "Root",
        foreign_keys="Article.root_id",
        backref=backref("articles", order_by=url),
    )

    def __repr__(self):
        return "Article(url='{0}', heading='{1}', scraped={2})".format(
            self.url, self.heading, self.scraped
        )


class Summary(Base):
    """Represents a summary of an article"""

    __tablename__ = "summaries"

    __table_args__ = (
        PrimaryKeyConstraint("article_id", "language", name="summaries_pkey"),
    )

    # The article UUID + the language code is the primary key
    article_id = Column(
        psql_UUID(as_uuid=False),
        ForeignKey("articles.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    # The language code is in a modified BCP 47 format, e.g. 'is_IS' or 'en_US'
    # (note underscore instead of hyphen)
    language = StringColumnRequired(8)

    # A summary of the article
    summary = StringColumnRequired()
    # The full text of the article
    text = StringColumn()
    # Summarization time stamp
    timestamp = DateTimeColumn()

    # The back-reference to the Root parent of this Article
    article: RelationshipProperty[Article] = relationship(
        "Article", backref=backref("summaries"),
    )


class Person(Base):
    """Represents a person"""

    __tablename__ = "persons"

    # Primary key
    id = cast(
        int,
        Column(
            Integer,
            Sequence("persons_id_seq"),  # type: ignore  # Don't ask me why
            primary_key=True,
        ),
    )

    # Foreign key to an article
    article_url = Column(
        String,
        # We don't delete associated persons if the article is deleted
        ForeignKey("articles.url", onupdate="CASCADE", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Name
    name = StringColumn(index=True)

    # Title
    title = StringColumn(index=True)
    # Title in all lowercase
    title_lc = StringColumn(index=True)

    # Gender
    gender = StringColumn(3, index=True)

    # Authority of this fact, 1.0 = most authoritative, 0.0 = least authoritative
    authority = FloatColumn()

    # Timestamp of this entry
    timestamp = DateTimeColumn()

    # The back-reference to the Article parent of this Person
    article: RelationshipProperty = relationship(  # type: ignore
        "Article", backref=backref("persons", order_by=name)  # type: ignore
    )

    def __repr__(self):
        return "Person(id='{0}', name='{1}', title={2})".format(
            self.id, self.name, self.title
        )


class Entity(Base):
    """Represents a named entity"""

    __tablename__ = "entities"

    # Primary key
    id = cast(
        int,
        Column(
            Integer,
            Sequence("entities_id_seq"),  # type: ignore  # Don't ask me why
            primary_key=True,
        ),
    )

    # Foreign key to an article
    article_url = Column(
        String,
        # We don't delete associated persons if the article is deleted
        ForeignKey("articles.url", onupdate="CASCADE", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Name
    name = Column(String, index=True)

    @hybrid_property
    def name_lc(self) -> str:
        return self.name.lower()

    @name_lc.comparator
    def name_lc(cls) -> Comparator:
        return CaseInsensitiveComparator(cls.name)

    # Verb ('er', 'var', 'sé')
    verb = StringColumn(index=True)
    # Entity definition
    definition = StringColumn(index=True)

    # Authority of this fact, 1.0 = most authoritative, 0.0 = least authoritative
    authority = FloatColumn()

    # Timestamp of this entry
    timestamp = DateTimeColumn()

    # The back-reference to the Article parent of this Entity
    article: RelationshipProperty[Article] = relationship(
        "Article", backref=backref("entities", order_by=name)
    )

    # Add an index on the entity name in lower case
    name_lc_index = Index("ix_entities_name_lc", func.lower(name))

    def __repr__(self):
        return "Entity(id='{0}', name='{1}', verb='{2}', definition='{3}')".format(
            self.id, self.name, self.verb, self.definition
        )


class Location(Base):
    """Represents a location"""

    __tablename__ = "locations"

    # UUID
    id = Column(
        psql_UUID(as_uuid=False),
        index=True,
        nullable=False,
        unique=True,
        primary_key=True,
        server_default=text("uuid_generate_v1()"),
    )

    # Foreign key to an article
    article_url = Column(
        String,
        # We don't delete associated location if the article is deleted
        ForeignKey("articles.url", onupdate="CASCADE", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Name
    name = StringColumn(index=True)

    # Kind (e.g. 'address', 'street', 'country', 'region', 'placename')
    kind = StringColumn(16, index=True)

    # Country (ISO 3166-1 alpha-2, e.g. 'IS')
    country = StringColumn(2)

    # Continent ISO code (e.g. 'EU')
    continent = StringColumn(2)

    # Coordinates (WGS84)
    latitude = FloatColumn()
    longitude = FloatColumn()

    # Additional data
    data = Column(JSONB)

    # Timestamp of this entry
    timestamp = DateTimeColumn()

    # The back-reference to the Article parent of this Location
    article = relationship("Article", backref=backref("locations", order_by=name))  # type: ignore

    __table_args__ = (UniqueConstraint("name", "kind", "article_url"),)

    def __repr__(self):
        return "Location(id='{0}', name='{1}', kind='{2}', country='{3}')".format(
            self.id, self.name, self.kind, self.country
        )


class Word(Base):
    """Represents a word occurring in an article"""

    __tablename__ = "words"

    MAX_WORD_LEN = 64

    # Foreign key to an article
    article_id = Column(
        psql_UUID(as_uuid=False),
        ForeignKey("articles.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )

    # The word stem
    stem = StringColumnRequired(MAX_WORD_LEN, index=True)

    # The word category
    cat = StringColumnRequired(16, index=True)

    # Count of occurrences
    cnt = IntegerColumnRequired()

    # The back-reference to the Article parent of this Word
    article: RelationshipProperty[Article] = relationship(
        "Article", backref=backref("words")
    )

    __table_args__ = (
        PrimaryKeyConstraint("article_id", "stem", "cat", name="words_pkey"),
    )

    def __repr__(self):
        return "Word(stem='{0}', cat='{1}', cnt='{2}')".format(
            self.stem, self.cat, self.cnt
        )


class Topic(Base):
    """Represents a topic for an article"""

    __tablename__ = "topics"

    id = Column(
        psql_UUID(as_uuid=False),
        server_default=text("uuid_generate_v1()"),
        primary_key=True,
    )

    # The topic name
    name = StringColumnRequired(128, index=True)

    # An identifier for the topic, such as 'sport', 'business'...
    # The identifier must be usable as a CSS class name.
    identifier = StringColumnRequired(32)

    # The topic keywords, in the form word1/cat word2/cat...
    keywords = StringColumnRequired()

    # The associated vector, in JSON format
    vector = StringColumn()  # Is initally NULL

    # The cosine distance threshold to apply for this topic
    threshold = FloatColumn()

    def __repr__(self):
        return "Topic(name='{0}')".format(self.name)


class ArticleTopic(Base):
    """Represents an article having a topic, a 1:N relationship"""

    __tablename__ = "atopics"

    article_id = Column(
        psql_UUID(as_uuid=False),
        ForeignKey("articles.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    topic_id = Column(
        psql_UUID(as_uuid=False),
        ForeignKey("topics.id", onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The back-reference to the Article parent of this ArticleTopic
    article: RelationshipProperty[Article] = relationship(
        "Article", backref=backref("atopics")
    )
    # The back-reference to the Topic parent of this ArticleTopic
    topic: RelationshipProperty[Topic] = relationship(
        "Topic", backref=backref("atopics")
    )

    __table_args__ = (
        PrimaryKeyConstraint("article_id", "topic_id", name="atopics_pkey"),
    )

    def __repr__(self):
        return "ArticleTopic()"


class Trigram(Base):
    """Represents a trigram of tokens from a parsed sentence"""

    __tablename__ = "trigrams"

    MAX_WORD_LEN = 64

    # Token 1
    t1 = Column(String(MAX_WORD_LEN), nullable=False)

    # Token 2
    t2 = Column(String(MAX_WORD_LEN), nullable=False)

    # Token 3
    t3 = Column(String(MAX_WORD_LEN), nullable=False)

    # Frequency
    frequency = Column(Integer, default=0, nullable=False)

    # The "upsert" query (see explanation below)
    _Q = """
        insert into trigrams as tg (t1, t2, t3, frequency) values(:t1, :t2, :t3, 1)
            on conflict (t1, t2, t3)
            do update set frequency = tg.frequency + 1;
        """
    # where tg.t1 = :t1 and tg.t2 = :t2 and tg.t3 = :t3;

    __table_args__ = (PrimaryKeyConstraint("t1", "t2", "t3", name="trigrams_pkey"),)

    @staticmethod
    def upsert(session: Session, t1: str, t2: str, t3: str) -> None:
        """Insert a trigram, or increment the frequency count if already present"""
        # The following code uses "upsert" functionality (INSERT...ON CONFLICT...DO UPDATE)
        # that was introduced in PostgreSQL 9.5. This means that the upsert runs on the
        # server side and is atomic, either an insert of a new trigram or an update of
        # the frequency count of an existing identical trigram.
        mwl = Trigram.MAX_WORD_LEN
        if len(t1) > mwl:
            t1 = t1[0:mwl]
        if len(t2) > mwl:
            t2 = t2[0:mwl]
        if len(t3) > mwl:
            t3 = t3[0:mwl]
        cast(Any, session).execute(Trigram._Q, dict(t1=t1, t2=t2, t3=t3))

    @staticmethod
    def delete_all(session: Session) -> None:
        """Delete all trigrams"""
        cast(Any, session).execute("delete from trigrams;")

    def __repr__(self):
        return "Trigram(t1='{0}', t2='{1}', t3='{2}')".format(self.t1, self.t2, self.t3)


class Link(Base):
    """Represents a (content-type, key) to URL mapping,
    usable for instance to cache image searches"""

    __tablename__ = "links"

    __table_args__ = (PrimaryKeyConstraint("ctype", "key", name="links_pkey"),)

    # Content type, for instance 'image' or 'text'
    ctype = Column(String(32), nullable=False, index=True)

    # Key, for instance a person name
    key = Column(String(256), nullable=False, index=True)

    # Associated content, often JSON
    content = Column(String)

    # Timestamp of this entry
    timestamp = Column(DateTime, nullable=False)

    def __repr__(self):
        return "Link(ctype='{0}', key='{1}', content='{2}', ts='{3}')".format(
            self.ctype, self.key, self.content, self.timestamp
        )


class BlacklistedLink(Base):
    """Represents a link blacklisted for a particular key"""

    __tablename__ = "blacklist"

    __table_args__ = (PrimaryKeyConstraint("key", "url", name="blacklisted_pkey"),)

    # Key, for instance a person name
    key = Column(String(256), nullable=False, index=True)

    # URL
    url = Column(String(2000), nullable=False, index=True)

    # Type (e.g. "image")
    link_type = Column(String(32))

    # Timestamp of this entry
    timestamp = Column(DateTime, nullable=False)

    def __repr__(self):
        return "BlacklistedLink(key='{0}', url='{1}', type='{2}', ts='{3}')".format(
            self.key, self.url, self.link_type, self.timestamp
        )


class Query(Base):
    """Represents a logged incoming query with its answer and client data."""

    __tablename__ = "queries"

    # UUID
    id = Column(
        psql_UUID(as_uuid=False),
        index=True,
        nullable=False,
        unique=True,
        primary_key=True,
        server_default=text("uuid_generate_v1()"),
    )

    # Timestamp of the incoming query
    timestamp = Column(DateTime, index=True, nullable=False)

    # Interpretations
    # JSON array containing list of possible interpretations
    # provided by a speech-to-text engine.
    interpretations = Column(JSONB, nullable=True)

    # Question
    question = Column(String, index=True, nullable=False)

    @hybrid_property
    def question_lc(self) -> str:
        return self.question.lower()

    @question_lc.comparator
    def question_lc(cls) -> Comparator:
        return CaseInsensitiveComparator(cls.question)

    # Beautified question
    bquestion = Column(String, index=False, nullable=True)

    # Answer
    answer = Column(String, index=False, nullable=True)

    @hybrid_property
    def answer_lc(self) -> str:
        return self.answer.lower()

    @answer_lc.comparator
    def answer_lc(cls) -> Comparator:
        return CaseInsensitiveComparator(cls.answer)

    # Voice answer
    voice = Column(String, index=False, nullable=True)

    @hybrid_property
    def voice_lc(self) -> str:
        return self.voice.lower()

    @voice_lc.comparator
    def voice_lc(cls) -> Comparator:
        return CaseInsensitiveComparator(cls.voice)

    # Error code
    error = cast(Optional[str], Column(String(256), nullable=True))

    # When does this answer expire, for caching purposes?
    # NULL=immediately
    expires = Column(DateTime, index=True, nullable=True)

    # The query type, NULL if not able to process
    qtype = Column(String(80), index=True, nullable=True)

    # The query key, NULL if not able to process or not applicable
    key = Column(String(256), index=True, nullable=True)

    # Client type
    # Either "www" (web interface), "ios" (iOS) or "android" (Android)
    client_type = Column(String(80), index=True, nullable=True)

    # Client version
    client_version = Column(String(10), nullable=True)

    # Client identifier, if applicable
    # If web client, this is the HTTP client user agent
    # On iOS and Android, this is a unique device UUID string
    client_id = Column(String(256), index=True, nullable=True)

    # Client location coordinates (WGS84)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    # Client IP address
    remote_addr = Column(INET, nullable=True)

    # Additional context used to answer the query
    context = Column(JSONB, nullable=True)

    # Add an index on the question in lower case
    question_lc_index = Index("ix_queries_question_lc", func.lower(question))

    # !!! The following indices don't work since answers can become
    # !!! very long (thousands of characters) and PostgreSQL has a
    # !!! limit on index entry size vs. its page size.

    # Add an index on the answer in lower case
    # answer_lc_index = Index('ix_queries_answer_lc', func.lower(answer))

    # Add an index on the voice answer in lower case
    # voice_lc_index = Index('ix_queries_voice_lc', func.lower(voice))

    def __repr__(self):
        return "Query(question='{0}', answer='{1}')".format(self.question, self.answer)


class QueryLog(Base):
    """Represents a fully anonymized, logged query and its answer."""

    __tablename__ = "querylog"

    # UUID
    id = Column(
        psql_UUID(as_uuid=False),
        index=True,
        nullable=False,
        unique=True,
        primary_key=True,
        server_default=text("uuid_generate_v1()"),
    )

    # See the Query class for documentation of these fields
    timestamp = Column(DateTime, index=True, nullable=False)

    interpretations = Column(JSONB, nullable=True)

    question = Column(String, index=True, nullable=False)

    bquestion = Column(String, index=False, nullable=True)

    answer = Column(String, index=False, nullable=True)

    voice = Column(String, index=False, nullable=True)

    qtype = Column(String(80), index=True, nullable=True)

    key = Column(String(256), index=True, nullable=True)

    error = Column(String(256), nullable=True)

    @staticmethod
    def from_Query(q: Query) -> QueryLog:
        """Create QueryLog object from Query object."""
        return QueryLog(
            timestamp=q.timestamp,
            interpretations=q.interpretations,
            question=q.question,
            bquestion=q.bquestion,
            answer=q.answer,
            voice=q.voice,
            qtype=q.qtype,
            key=q.key,
            error=q.error,
        )

    def __repr__(self):
        return "QueryLog(question='{0}', answer='{1}')".format(
            self.question, self.answer
        )


class QueryData(Base):
    """Represents client data saved from a processed query."""

    __tablename__ = "querydata"

    __table_args__ = (PrimaryKeyConstraint("client_id", "key", name="querydata_pkey"),)

    client_id = cast(str, Column(String(256), nullable=False))

    # Key to distinguish between different types of JSON data that can be stored
    key = cast(str, Column(String(64), nullable=False))

    # Created timestamp
    created = cast(datetime, Column(DateTime, nullable=False))

    # Last modified timestamp
    modified = cast(datetime, Column(DateTime, nullable=False))

    # JSON data
    data = cast(Any, Column(JSONB, nullable=False))

    def __repr__(self):
        return "QueryData(client_id='{0}', created='{1}', modified='{2}', key='{3}', data='{4}')".format(
            self.client_id, self.created, self.modified, self.key, self.data
        )


class Feedback(Base):
    """Represents a feedback form submission."""

    __tablename__ = "feedback"

    # UUID
    id = Column(
        psql_UUID(as_uuid=False),
        index=True,
        nullable=False,
        unique=True,
        primary_key=True,
        server_default=text("uuid_generate_v1()"),
    )

    # Timestamp of feedback
    timestamp = Column(DateTime, index=True, nullable=False)

    # Topic (e.g. Embla/Netskrafl/etc.)
    topic = Column(String, index=True, nullable=True)

    # Name
    name = Column(String, index=True, nullable=True)

    # Email
    email = Column(String, index=True, nullable=True)

    # Comment
    comment = Column(String, index=False, nullable=True)

    def __repr__(self):
        return "Feedback(name='{0}', email='{1}', topic='{2}', comment='{3}')".format(
            self.name, self.email, self.topic, self.comment
        )
