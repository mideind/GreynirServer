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

5. **Index** ☑ 2026-08-17:

   ```sql
   SET maintenance_work_mem = '2GB';   -- build is much slower without it
   CREATE INDEX CONCURRENTLY articles_topic_embedding_hnsw
     ON articles USING hnsw (topic_embedding vector_cosine_ops);
   ```

   HNSW over IVFFlat: better recall and latency, no training step, and it
   handles incremental inserts — which matters because new articles arrive
   continuously. `CONCURRENTLY` because the table serves production while it
   runs. The name matches the model's `articles_topic_embedding_hnsw` so
   `create_all` on a fresh database and the hand-built production index
   agree.

   Outcome: the default-parameter build took ~9 minutes and produced
   1,597 MB, with ~7 ms queries against simserver's ~325 ms median — but
   recall measurement against exact (seqscan) ground truth exposed a bad
   tail: mean recall@10 was 0.966 yet some articles scored **zero**, with
   their true neighbours unreachable even at `hnsw.ef_search = 100`. Root
   cause: 73,326 rows share byte-identical embeddings (32,859 duplicate
   groups; the largest is 1,603 copies of one vector — verbatim wire copies
   and near-empty articles), and dense clusters of identical points break
   HNSW graph connectivity when built with default parameters, stranding
   nodes on graph "islands".

   The index was therefore rebuilt with `WITH (m = 24, ef_construction =
   200)` — more and better-chosen edges per node, the standard mitigation —
   built concurrently alongside the old one and measured before switching:
   ~44 minutes, 1,862 MB, and recall@10 vs exact went from mean 0.966 /
   min 0.00 to **mean 0.986 / min 0.80** at ef_search=40, and 0.992 / 0.80
   at ef_search=100. The previously pathological articles now return the
   exact ground-truth top-8. The old index was dropped and the new one
   renamed to the canonical `articles_topic_embedding_hnsw`; the model's
   Index() carries the same parameters via `postgresql_with`.

   Operational notes: `CREATE INDEX CONCURRENTLY` must be launched from a
   session that nothing will kill mid-flight — a first attempt under a
   10-minute client timeout was cancelled and left an INVALID index, which
   had to be dropped (`DROP INDEX CONCURRENTLY`) before retrying detached.
   And 2 GB of `maintenance_work_mem` does not hold the m=24 graph of 1.47M
   vectors; the build spills and slows, which is where most of the 44
   minutes went.

**Phase 1 is complete.** The embedding column is live, trigger-maintained,
fully backfilled and indexed; nothing yet reads it. Phase 2 (cutting the
`id` and `topic` read paths over to SQL) is next.

## Phase 2 — read-path cutover for `id` and `topic`, with A/B verification

**☑ Live in production since 2026-08-18.** Staging and production were
deployed and checked; a warm `/similar` request completes in ~80 ms
end-to-end over HTTPS, versus ~325 ms previously for the kNN computation
alone. Rolling back is redeploying the previous commit (`ea79edb6^`); the
database changes are inert under the old code. simserver now serves only
the low-volume `terms` path.

Deployment note: `/home/greynir/github/Greynir` (the deploy/pipeline
checkout) had an SSH origin that cannot authenticate under
`sudo -u greynir`; since the repo is public and that checkout is
pull-only, its origin was switched to https on 2026-08-18.

What was done, in `search.py`:

- `list_similar_to_article` and `list_similar_to_topic` are now direct SQL:
  kNN via `<=>` (similarity = `1 - distance`) joined with `roots` and
  hydrated in the same query, `LIMIT n + 5`, preserving simserver's
  semantics — the `Root.visible` filter, the `similarity > 0.9999`
  self/verbatim-copy drop, and the same-domain near-duplicate collapse
  (extracted into `_filter_candidates`, shared by all three paths).
  An invalid or unknown uuid, or an article without an embedding, reports
  `not_indexed` exactly as before. The query runs with
  `SET LOCAL hnsw.ef_search = 100` (see the recall numbers under phase 1).
- The N+1 hydration is gone everywhere: the kNN paths hydrate in the kNN
  query itself, and the `terms` path (still simserver, until phase 3) bulk
  fetches all candidates in one `id = ANY(...)` query inside
  `list_articles`.
- `similar.py` and the `SimilarityClient` remain, used only by the `terms`
  path.

Verification against the live database:

- Functional: all paths exercised — article, unknown uuid, invalid uuid
  text, faulty-vector article, topic vector, zero vector, terms — with
  expected results and `not_indexed` flags.
- A/B vs simserver, 200 random articles, final index, ef_search=100:
  top-10 overlap mean **0.990**, median 1.000, 198/200 at ≥ 0.9;
  similarity values agree to 6 decimals on common ids. The two sub-0.9
  cases are articles inside exact-duplicate embedding clusters, where both
  systems return an arbitrary selection of similarity-1.0 ties — and the
  app filters everything above 0.9999 as a verbatim copy anyway, so the
  user-visible output is unaffected.
- During the A/B, simserver and exact pg search were also cross-checked and
  agree perfectly; an apparent simserver staleness in an early reading of
  the diff was a misreading, not a real discrepancy.

After the deploy, simserver's load drops to the low-volume `terms` path
only, and phase 3 can retire it at leisure.

## Phase 3 — the `terms` path

**Code complete and verified 2026-08-18; goes live at the next web deploy,
after the model files are copied into the deployments (see below).**

`ReynirCorpus.get_topic_vector` was the only query-time Gensim dependency.
Its math turned out to be exactly as small as predicted: dictionary lookup
(`doc2bow`) → tf-idf weighting with L2 normalization → one matrix multiply
against the LSI projection (`u.T @ x`, unscaled), plus a words-table
fallback that is pure SQL + numpy.

What was done:

- `tools/export_lsi_model.py` (runs under the 3.9 venv, which has gensim,
  with `vectors/` as cwd — unpickling `reynir.dict` imports `builder.py`)
  exports `resources/lsi/`: `token2id.json` (82,856 terms), `idfs.npy`,
  `u.npy` (82,856 × 200 float32, ~66 MB), `meta.json`, and
  `reference.json` — gensim's own outputs for 22 sample token lists.
- `topicvector.py` reimplements the pipeline gensim-free: lazy singleton,
  `u.npy` loaded with `mmap_mode="r"` so gunicorn workers share pages, and
  a faithful port of `get_topic_vector`'s term-weight logic (2.0 for
  person/entity, 1.6 for capitalized non-initial nouns, 1.2 for
  out-of-dictionary terms, words-table averaging via `TermTopicsQuery`).
  One deliberate fix over the original: malformed 199-element stored
  vectors are skipped in the fallback averaging, where `builder.py` would
  have crashed on a shape mismatch.
- `search.py`'s `list_similar_to_terms` now projects locally and runs the
  same pgvector kNN as the other paths. The web app no longer imports
  `SimilarityClient`; missing model files degrade exactly like an
  unreachable simserver used to (empty weights → caller raises).
- `numpy` is now an explicit dependency (it was only transitive before).

Verification:

- `topicvector.LsiModel.project` reproduces gensim's reference outputs to
  max abs error 8e-10 (max relative 8e-8, from the float32 projection
  matrix).
- End-to-end A/B against the live simserver on six term queries covering
  every code path (dictionary terms, person, entity, capitalized noun,
  NoIndexWords-suppressed term, nonsense term): term weights identical,
  top-10 article overlap 1.00 on every case with results.

The `resources/lsi/` files are gitignored and deployed out-of-band, like
API keys. **Before the next deploy**, copy them into both deployments:

```bash
sudo -u greynir cp -r /home/villi/github/GreynirServer/resources/lsi \
    /usr/share/nginx/greynir.is/resources/
sudo -u greynir cp -r /home/villi/github/GreynirServer/resources/lsi \
    /usr/share/nginx/staging.greynir.is/resources/
```

If the LSI model is ever rebuilt (`builder.py model`), the export must be
re-run and re-copied; `meta.json` records provenance.

Note: the topic **tagger** needs Gensim regardless of anything in this plan —
it produces the vectors. It stays on the 3.9 venv until/unless the embedding
strategy itself changes (see "Vör" below).

## Phase 4 — decommission ☐

Prerequisite: phase 3 deployed and the production search box verified.
Then, in order:

1. `sudo systemctl stop similarity && sudo systemctl disable similarity` —
   nothing calls it any more. This also retires the 16-minute warm-up
   gotcha and most of the 476 MB/rotation syslog volume.
2. Remove the `--notify`/`-n` flag from the tagger invocation in greynir's
   crontab (it pings the now-dead similarity server; `builder.py` catches
   the failure and just logs noise, but the noise is pointless).
3. Repo cleanup commit: delete `vectors/simserver.py` and `similar.py`,
   drop `notify_similarity_server()` and the `--notify` option from
   `vectors/builder.py` (a 3.9-compatible edit), and drop the
   `SIMSERVER_HOST`/`SIMSERVER_PORT` settings. `git pull` the pipeline
   checkout afterwards.
4. Delete `resources/SimilarityServerKey.txt` from the deployments and the
   pipeline checkout, and the stale `/usr/share/nginx/*/vectors/` copies.
5. Update the machine PLAN.md service inventory (gotcha 9, the warm-up
   note, the syslog note) — simserver no longer exists.
- **Keep `articles.topic_vector` (the JSON column) indefinitely.** It is the
  source of truth for the backfill, the rollback path, and what the 3.9 tagger
  writes. `topic_embedding` is derived state.

Rollback at any point before phase 4's deletions: the old path is untouched —
redeploy the previous commit, and simserver (or a restart of it) serves as
before.

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
