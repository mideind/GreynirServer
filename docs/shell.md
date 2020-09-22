# Using the Greynir Shell

To start the Greynir shell, activate the virtual environment and install IPython:

```
pip install ipython
```

You can then run the following command from the repository root:

```
scripts/shell.sh 
```

This will launch an [IPython](http://ipython.readthedocs.io) shell, a superior alternative to the standard Python REPL. Features include syntax highlighting, auto-pretty-printing, auto-indentation, smart autocompletion, persistent history across sessions, integrated access to pdb and the profiler, and various introspection tools.

To enable auto-reloading of modules prior to every command, run the following command: 

```
%autoreload 2
```

The shell has been configured to automatically import Greynir's database models and create a (commit-disabled) database session when launched. The Greynir parser is also imported.

* `s` - SQLAlchemy database session
* `g` - Instance of the [Greynir](https://github.com/mideind/GreynirPackage) parser.

For an overview of Greynir's database models, see `db/models.py`.

Shell auto-imports are configured in `.ipython.py` in the repository root. Additional local user settings can be configured in `~/.ipython/profile_default`.

### Querying the database

Get the titles of recent articles:

```
In [1]: s.query(Article.heading).order_by(desc(Article.timestamp)) \
   ...: .limit(5).all()
Out[1]:
[('Guðjón Pétur í KA'),
 ('Parkland-ungmennin sem breyttu heiminum'),
 ('Airwaves-helgin gerð upp'),
 ('Sturridge í vondum málum?'),
 ('Óttar ekki áfram hjá Trelleborg')]
```

Show recent persons identified by Greynir's Named Entity Recognition module:

```
In [1]: s.query(Person.name, Person.title) \
   ...: .order_by(Person.timestamp).limit(5).all()
Out[6]:
[('Þórður Snær Júlíusson', 'ritstjóri Kjarnans'),
 ('Jón Magnús Kristjánsson', 'yfirlæknir bráðalækninga á Landspítalanum'),
 ('Davíð Oddsson', 'ritstjóri Morgunblaðsins'),
 ('Þórdís Kolbrún Reykfjörð Gylfadóttir', 'varaformaður Sjálfstæðisflokksins'),
 ('Ingólfur Helgason', 'fyrrverandi forstjóri Kaupþings á Íslandi')]
```

### Parsing with Greynir

```
In [1]: sent = g.parse_single("Mikið væri það skemmtilegt fyrir Gunna.")
In [2]: print(sent.tree.view)
Out[2]:
P
+-S-MAIN
  +-IP
    +-ADVP
      +-ao: 'Mikið'
    +-VP-SEQ
      +-VP
        +-so_et_p3: 'væri'
        +-NP-SUBJ
          +-pfn_hk_et_nf: 'það'
        +-ADJP
          +-lo_sb_nf_et_hk: 'skemmtilegt'
      +-PP
        +-fs_þf: 'fyrir'
        +-NP
          +-person_þf_kk: 'Gunna'
+-'.'
In [3]: sent.tree.nouns
Out[3]: ['Gunni']
In [4]: sent.tree.lemmas
Out[4]: ['mikið', 'vera', 'það', 'skemmtilegur', 'fyrir', 'Gunni', '.']

```
