# PLAN.md — Similarity search: retire simserver for pgvector

This is the working plan for moving Greynir's similar-articles feature off the
custom in-memory similarity server (`vectors/simserver.py`) and onto
PostgreSQL's `pgvector` extension. It lives in this repository because the work
is chiefly a GreynirServer code change; the machine-wide context (PG17
migration, service inventory, hardening) is in `/home/villi/PLAN.md` on
`frida.mideind.is`, whose §3.7 originated this plan and now defers to this
document.

Status legend: ☐ pending, ☑ done (with date).

## Why

`simserver.py` is a hand-written brute-force kNN: every query streams a
~1.5M × 200 float32 matrix (~1.2 GB) through numpy and argpartitions it, at a
median ~325 ms. It is a single Python process holding ~2 GB (much of it
observed in swap), with a ~16-minute warm-up during which it does not serve, a
bespoke `multiprocessing.connection` protocol over a shared-secret TCP socket,
and a history of freezing gunicorn workers under gevent (see the 2026-08-02
outage notes in `similar.py` and `vectors/simserver.py`). An HNSW index answers
the same question in about a millisecond, inside postgres — shared,
multi-process, warm across restarts.

**No re-embedding is required.** pgvector indexes whatever float arrays it is
given; it does not care that ours come from a Gensim LSI model rather than a
neural embedding. The vectors already live in the `articles.topic_vector`
column as JSON array text, which is byte-for-byte pgvector's text input format,
so the backfill is a straight `::vector` cast. The Gensim model is needed only
to *produce* vectors — the topic tagger (`vectors/builder.py`), which keeps
running unchanged on its CPython 3.9 venv — and to project free-text search
terms into LSI space (phase 3 below). The hot path, "similar to article X", is
a lookup of X's stored vector plus a cosine kNN: one SQL query.

## Verified facts

| fact | value | verified |
|---|---|---|
| vector dimensions | 200, float32 (`vectors/builder.py`, `_DEFAULT_DIMENSIONS`) | 2026-08-02 |
| stored as | `articles.topic_vector`, `character varying`, JSON array text | 2026-08-02 |
| rows with vectors | 1,469,495 of 1,500,407 articles | 2026-08-17 |
| dims on 20,000-row sample | all exactly 200 | 2026-08-17 |
| pgvector | 0.8.6 (`postgresql-17-pgvector`), extension created in `scraper` | 2026-08-17 |
| postgres | 17.10 | 2026-08-17 |
| query traffic | the `id=<uuid>` path is essentially all of it; `terms` (search box) is low-volume | 2026-08-02 |

Historical caveat: the tagger has logged "faulty topic vector" warnings in the
past, so the backfill must not assume every stored vector is well-formed — one
bad row in an unguarded `UPDATE … ::vector` batch aborts the whole batch.

## The one real complication: three query paths, not one

| path | caller | needs |
|---|---|---|
| `id=<uuid>` | `/similar` route → `Search.list_similar_to_article` | nothing but stored vectors — ports cleanly |
| `topic=[...]` | `Search.list_similar_to_topic` | caller supplies the vector — ports cleanly |
| `terms=[...]` | `queries/builtin.py` → `Search.list_similar_to_terms` | the Gensim LSI model in-process (`ReynirCorpus.get_topic_vector`) — does **not** port directly |

The `terms` path is the reason `vectors/` cannot simply be deleted on day one,
and the reason the migration is phased: moving `id` and `topic` first removes
effectively all the load, and `terms` is dealt with separately in phase 3.

## Phase 0 — install ☑ 2026-08-17

`postgresql-17-pgvector` installed via apt; `CREATE EXTENSION vector` run in
the `scraper` database. Machine-wide step, recorded here for completeness.

## Phase 1 — column, sync trigger, backfill, index

1. **Column** ☑ 2026-08-17:

   ```sql
   ALTER TABLE articles ADD COLUMN topic_embedding vector(200);
   ```

2. **Sync trigger, not a write-path code change** ☑ 2026-08-17. The only place
   a vector is persisted is `vectors/builder.py` (`assign_article_topics`),
   which runs from the frozen CPython 3.9 venv. Editing it was considered and
   ruled out: it would drag a pgvector client dependency into an environment
   that is deliberately never touched (see CLAUDE.md on `vectors/`), and any
   skew between "tagger writes both columns" and "backfill fills old rows" is
   a correctness hazard during the transition. A trigger keeps the 3.9 world
   byte-identical, costs one cast per tagged article (a few hundred per day),
   and closes the backfill/cutover gap automatically.

   The applied form guards with an exception handler, not a JSON pre-check:
   pgvector's input function has no soft-error support (`pg_input_is_valid`
   raises instead of returning false — verified on 0.8.6), and a malformed
   vector must yield NULL rather than abort the tagger's transaction:

   ```sql
   CREATE OR REPLACE FUNCTION public.sync_topic_embedding() RETURNS trigger
   LANGUAGE plpgsql AS $$
   BEGIN
     IF NEW.topic_vector IS NULL THEN
       NEW.topic_embedding := NULL;
     ELSE
       BEGIN
         NEW.topic_embedding := NEW.topic_vector::public.vector;
       EXCEPTION WHEN OTHERS THEN
         NEW.topic_embedding := NULL;
       END;
     END IF;
     RETURN NEW;
   END $$;

   CREATE TRIGGER trg_sync_topic_embedding
     BEFORE INSERT OR UPDATE OF topic_vector ON articles
     FOR EACH ROW EXECUTE FUNCTION public.sync_topic_embedding();
   ```

   Verified live: a self-assignment `UPDATE ... SET topic_vector =
   topic_vector` on one row populated `topic_embedding` with the expected
   200-dim value.

3. **Schema-as-code** ☑ 2026-08-17. A fresh database built by
   `scraper.py --init` → `Base.metadata.create_all()` now gets all of the
   above: `db/models.py` defines a minimal `Vector` UserDefinedType (pure
   SQLAlchemy 1.4, importable on the 3.9 venv — deliberately not
   pgvector-python), the `topic_embedding` column, the HNSW index in
   `__table_args__`, and `event.listen` DDL for `CREATE EXTENSION IF NOT
   EXISTS vector` plus the trigger. CI's postgres service image moved from
   `postgres:15` to `pgvector/pgvector:pg17` (plain postgres images do not
   ship pgvector; pg17 also matches production), and both CI and
   `scripts/test_local.sh` create the extension during database setup, like
   `uuid-ossp`. Local test runs need `postgresql-17-pgvector` installed.

4. **Backfill, batched and guarded** ☑ 2026-08-17. ~1.5M rows in id-ordered
   batches of 5,000, paginated by `id > last` (not by `topic_embedding IS
   NULL`, so a skipped bad row cannot loop forever). Guarded by a nested-CASE
   predicate — `pg_input_is_valid(tv,'json')`, then `json_typeof = 'array'`,
   then `json_array_length = 200` — nested CASE rather than AND because AND
   does not guarantee evaluation order and the later checks raise on inputs
   the earlier ones reject. Cast verified on 10 rows by hand first.

   Outcome (2026-08-17): 1,469,493 of 1,469,510 vectored rows embedded in
   ~21 minutes. The 17 skipped rows are valid JSON arrays of **199** elements
   — the same pre-existing faulty vectors simserver warns about and skips
   (it, too, requires exactly 200), so behaviour is preserved: those articles
   stay out of similarity results. Root cause is almost certainly gensim
   returning a sparse LSI result that omits a near-zero component while
   `builder.py` stores only the values, so the stored 199 floats may even be
   misaligned; the fix, if ever wanted, is re-tagging those 17 articles
   (`builder.py tag <uuid>`), not repairing the stored text.

5. **Index** ☐:

   ```sql
   SET maintenance_work_mem = '2GB';   -- build is much slower without it
   CREATE INDEX CONCURRENTLY articles_topic_embedding_hnsw
     ON articles USING hnsw (topic_embedding vector_cosine_ops);
   ```

   HNSW over IVFFlat: better recall and latency, no training step, and it
   handles incremental inserts — which matters because new articles arrive
   continuously. Expect a long build; `CONCURRENTLY` because the table serves
   production while it runs. Expected index size roughly 1.5–2 GB. The name
   must match the model's `articles_topic_embedding_hnsw` so `create_all` on
   a fresh database and the hand-built production index agree.

## Phase 2 — read-path cutover for `id` and `topic`, with A/B verification ☐

Rewrite `Search.list_similar_to_article` (`search.py:74`) and
`Search.list_similar_to_topic` (`search.py:90`) as direct SQL. Cosine distance
is `<=>`, so similarity is `1 - distance`:

```sql
SELECT a.id, 1 - (a.topic_embedding <=> $1) AS similarity
  FROM articles a JOIN roots r ON r.id = a.root_id
 WHERE r.visible AND a.topic_embedding IS NOT NULL
 ORDER BY a.topic_embedding <=> $1
 LIMIT $2;
```

- **Preserve simserver's semantics:** it filters `Root.visible`
  (`db/models.py:163`), and `search.py` drops results with
  `similarity > 0.9999` (the article itself or a verbatim copy). The existing
  `n + 5` over-fetch covers that. The `visible` filter passes ~98% of rows, so
  filtered HNSW scans are a non-issue on pgvector 0.8.
- **Collapse the N+1 while there.** `Search.list_articles` (`search.py:120`)
  currently issues one query per result to hydrate each article; with pgvector
  the kNN and the hydration are the same query. A free latency win.
- **A/B verify before trusting it.** simserver keeps running through this
  phase. Compare pgvector's top-10 against simserver's for a few hundred
  sample articles. Expect high but not perfect overlap: HNSW is approximate
  (recall tunable via `hnsw.ef_search`), and that is fine for a
  similar-articles list — but establish it by measurement, not assumption.
- Line numbers above verified 2026-08-17.

## Phase 3 — the `terms` path ☐

`ReynirCorpus.get_topic_vector` is the only query-time Gensim dependency. Its
actual math is small: dictionary lookup (`doc2bow`) → tf-idf weighting → one
matrix multiply against the LSI projection (`lsi-200.model.projection.u`,
vocab × 200), plus a words-table fallback that is already pure SQL + numpy.
Only ~135 MB of the model files are needed for inference.

Preferred: **export the dictionary (token→id), idf weights, and projection
matrix as plain numpy files and reimplement those ~30 lines Gensim-free** in
the web app on CPython 3.14 (lazy-loaded on first search-box use). This kills
Gensim from the query path without a gensim-4 port and without keeping any
extra service alive. The projection matrix is ~160 MB float32; if per-worker
copies are unacceptable, mmap it read-only so workers share pages.

Ruled out / fallback options, in order:

1. A slim terms→vector service on the 3.9 venv (no matrix, no warm-up) — the
   previous preference; still viable as an interim if the export takes longer
   than expected, but it keeps a bespoke service and socket alive.
2. Porting gensim 3.8.2 to run on 3.14 — a gensim 4.x port, judged not worth it
   for 30 lines of linear algebra.
3. Accepting that search-by-terms is unavailable — only as a temporary state.

Until phase 3 lands, either keep simserver alive solely for `terms`, or accept
the degraded search box briefly.

Note: the topic **tagger** needs Gensim regardless of anything in this plan —
it produces the vectors. It stays on the 3.9 venv until/unless the embedding
strategy itself changes (see "Vör" below).

## Phase 4 — decommission ☐

- `similarity.service` (systemd unit) — its retirement also deletes the
  16-minute warm-up gotcha and most of the 476 MB/rotation syslog volume.
- `vectors/simserver.py`, `similar.py` (`SimilarityClient` becomes dead code),
  `resources/SimilarityServerKey.txt` and its shared-secret handling.
- The stale `/usr/share/nginx/*/vectors/simserver.py` copies.
- **Keep `articles.topic_vector` (the JSON column) indefinitely.** It is the
  source of truth for the backfill, the rollback path, and what the 3.9 tagger
  writes. `topic_embedding` is derived state.

Rollback at any point before phase 4: the old path is untouched — stop routing
queries to SQL, and simserver (or a restart of it) serves as before.

## Out of scope: the Vör / Gemini embeddings

Vör (`vthorsteinsson/vor-news`) re-embeds Greynir articles with Google's Gemini
embedding model (1536 dims) into a separate database on `brandur.mideind.is`.
Considered and deliberately kept **out of this migration**: it is a different
semantic space, so using it here would mean re-embedding the coverage gap,
changing result semantics, putting a Google API call into the scrape pipeline,
and redesigning topic tagging (topics are LSI keyword vectors). None of that is
needed to retire simserver.

It remains interesting as a *separate, later* decision, because it is the only
path that ever fully retires Gensim and the 3.9 venv — tagger included.
pgvector makes coexistence trivial: a second column (e.g.
`semantic_embedding vector(768)`; 1536 is overkill — Gemini embeddings support
Matryoshka truncation to 768 with renormalization) can sit beside the LSI one,
and the two schemes can be compared on live traffic before either is retired.

## Expectations

- **Latency:** ~325 ms median → ~1 ms, and no longer a serialised resource.
- **Memory:** ~1.15 GB of vectors plus 50–100% HNSW overhead, inside postgres
  buffer cache — comparable to simserver's 2 GB, but shared, not swapped, and
  warm across restarts.
- **Freshness:** no refresh/notify machinery; the trigger keeps the embedding
  column current the moment the tagger commits.
