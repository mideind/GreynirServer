import datetime
import json
import sys

import sqlalchemy
import uuid
from sqlalchemy.dialects.postgresql import UUID as psql_UUID

from db import SessionContext, DataError, desc
from db.models import Article as ArticleRow, Word, Root
from article import Article


def gen_sent_text(art):
    tokens = json.loads(art.tokens)
    idx = 0
    for pg in tokens:
        for sent in pg:
            sent_text = [tok["x"] for tok in sent]
            sent_text = " ".join(sent_text)
            yield sent_text


def get_article_from_id(uid):
    with SessionContext(commit=True, read_only=True, session=None) as session:
        q = session.query(ArticleRow)
        puid = psql_UUID(uid)
        arow = q.filter(ArticleRow.id == uid).first()
        return  Article._init_from_row(arow)


def dump_html(uid):
    art = get_article_from_id(uid)
    print(art.html)


def explore(uid):
    art = get_article_from_id(uid)
    dt = art._scraped
    print(dt)
    import pdb; pdb.set_trace(); _ = 1 + 1


def main(uid, idx):
    art = get_article_from_id(uid)
    # _idx is zero indexed
    context_size = 30
    segs = [(_idx + 1, line) for (_idx, line) 
        in enumerate(gen_sent_text(art))
        if abs(idx - (_idx + 1)) < context_size
    ]
    if not segs:
        print("No article found.")
        sys.exit(0)
    for (it, line) in segs:
        if idx == it:
            pointer = "-" * len(str(idx))
            print(pointer, line, sep="\t")
        else:
            print(it, line, sep="\t")


if __name__ == '__main__':
    uid, idx = sys.argv[1:3]
    idx = int(idx)
    main(uid, idx)
    #explore(uid)


