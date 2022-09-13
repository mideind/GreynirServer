
# Vectors directory

## Text similarity functionality of Greynir

This directory contains most of the text similarity
functionality of Greynir. This functionality allows topic
vectors (lists of 200 floats) to be calculated, e.g. for articles,
word lists and search terms. The topic vectors can then be
compared, for instance with cosine similarity, to determine
how closely related the associated texts are.

This code uses Radim Rehurek's
[Gensim](https://radimrehurek.com/gensim/auto_examples/index.html).
The link points to a highly recommended tutorial on
topic models, TF-IDF and LSI.

### Setup

In addition to the files found here in this repository,
you will need the following:

*  A CPython >=3.7 virtualenv within the `vectors` folder, typically
   called `venv`. (PyPy presently doesn't support
   `numpy` and `gensim` adequately for this purpose,
   so CPython is required.)

*  Within the venv, you need to `pip install -r requirements.txt`

*  You also need soft links to the following files and directories
   from the parent Greynir directory:

   ```bash
   ln -s ../db .
   ln -s ../settings.py .
   ln -s ../similar.py .
   ```

After this is all set up, you can select your venv and use
`builder.py` to access the text similarity functionality:

```bash
source venv/bin/activate
python builder.py --help
```

To rebuild a dictionary and TF-IDF and LSI models from your
text corpus (by default coming from the `articles` database table
in the PostgreSQL database `scraper`):

```bash
python builder.py model
```

To generate topic vectors for the topics in the `Topics.conf` file,
and store them in the database `topics` table, invoke:

```bash
python builder.py topics
```

