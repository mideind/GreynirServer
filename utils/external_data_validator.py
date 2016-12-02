import os
import codecs
import sys

cwd = os.path.dirname(__file__)

def run_txt_parser(file):
    """ Read input file and output CSV """
    out = codecs.open(file['outfile'], 'a', 'utf-8')
    header_skip = file['start-line']
    with codecs.open(file['infile'], 'r', 'iso-8859-1') as inp:
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

def run_csv_parser(file):

    header_skip = file['start-line']
    out = codecs.open(file['outfile'], 'a', file['out-encoding'])

    with codecs.open(file['infile'], 'r', file['in-encoding']) as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if line.split() and i >= header_skip:
                out.write(line)

files = [
    {
        'infile': cwd+'../resources/plastur.feb2013.txt',
        'outfile': cwd+'../resources/ord.csv',
        'in-encoding': 'iso-8859-1',
        'out-encoding': 'utf-8',
        'start-line': 33,
        'func': run_csv_parser
    },
    {
        'infile': cwd + '../resources/SHsnid.csv',
        'outfile': cwd+'../resources/ord.csv',
        'in-encoding': 'utf-8',
        'out-encoding': 'utf-8',
        'start-line': 0,
        'func': run_csv_parser
    },    
    {
        'infile': cwd + '../resources/obeyg.smaord.txt',
        'outfile': cwd+'../resources/ord.csv',
        'in-encoding': 'iso-8859-1',
        'out-encoding': 'utf-8',
        'start-line': 38,
        'func': run_txt_parser
    },     
]


if __name__ == '__main__':
    for file in files:
        if not os.path.isfile(file['infile']):            
            sys.exit('Neccessary file is missing: {}'.format(file['infile']))
        else:
            print('Retrieving data from file: {}'.format(file['infile']))
            file['func'](file)
            print('Data appended successfully to file: {}'.format(file['outfile']))
    print('And we are done :D')