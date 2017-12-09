import os
import codecs
import sys

cwd = os.path.dirname(__file__)

def run_txt_parser(file, append):
    """ Read input file and output CSV """
    with codecs.open(file['outfile'], 'a' if append else 'w', file['out-encoding']) as out:
        header_skip = file['start-line']
        with codecs.open(file['infile'], 'r', file['in-encoding']) as inp:
            for li in inp:
                if header_skip:
                    header_skip -= 1
                    continue
                if li:
                    li = li.strip()
                if li:
                    if not li.startswith('#'):
                        forms = li.split(u' ')
                        if forms:                        
                            word = forms[0]
                            for f in forms[1:]:
                                s = u'{0};{1};{2};{3};{4};{5}\n'.format(
                                    word, 0, f, u'ob', word, u'-'
                                )                                                
                                out.write(s)

def run_csv_parser(file, append):
    header_skip = file['start-line']
    with codecs.open(file['outfile'], 'a' if append else 'w', file['out-encoding']) as out:
        with codecs.open(file['infile'], 'r', file['in-encoding']) as f:
            for i, line in enumerate(f):
                if i >= header_skip:
                    if line.strip():
                        out.write(line)

files = [
    {
        'infile': cwd + '../resources/plastur.feb2013.txt',
        'outfile': cwd + '../resources/ord.csv',
        'in-encoding': 'iso-8859-1',
        'out-encoding': 'utf-8',
        'start-line': 33,
        'func': run_csv_parser
    },
    {
        'infile': cwd + '../resources/SHsnid.csv',
        'outfile': cwd + '../resources/ord.csv',
        'in-encoding': 'utf-8',
        'out-encoding': 'utf-8',
        'start-line': 0,
        'func': run_csv_parser
    },
    {
        'infile': cwd + '../resources/obeygd.hreinsad.txt',
        'outfile': cwd + '../resources/ord.csv',
        'in-encoding': 'utf-8',
        'out-encoding': 'utf-8',
        'start-line': 0,
        'func': run_txt_parser
    },
]


if __name__ == '__main__':

    # Start with a sanity check
    for file in files:
        if not os.path.isfile(file['infile']):            
            sys.exit('Necessary file is missing: {}'.format(file['infile']))

    append = False
    for file in files:
        print('Retrieving data from file: {}'.format(file['infile']))
        file['func'](file, append)
        print('Data {0} successfully to file: {1}'
            .format("appended" if append else "written", file['outfile']))
        append = True

    print('And we are done :D')