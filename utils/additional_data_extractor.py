import os
import codecs
import sys

cwd = os.path.dirname(__file__)

files = [
    {
        'infile': cwd+'../resources/plastur.feb2013.txt',
        'outfile': cwd+'../resources/ord.csv',
        'in-encoding': 'iso-8859-1',
        'out-encoding': 'utf-8',
        'start-line': 33
    },
    {
        'infile': cwd + '../resources/SHsnid.csv',
        'outfile': cwd+'../resources/ord.csv',
        'in-encoding': 'utf-8',
        'out-encoding': 'utf-8',
        'start-line': 0
    },    
]

def run():

    for file in files:

        out = codecs.open(file['outfile'], 'a', file['out-encoding'])

        with codecs.open(file['infile'], 'r', file['in-encoding']) as f:
            lines = f.readlines()
            for i, line in enumerate(lines):
                if line.split() and i >= file['start-line']:
                    #print(i, line)
                    out.write(line)

if __name__ == '__main__':
    for file in files:
        if not os.path.isfile(file['infile']):            
            sys.exit('Neccessary file is missing: {}'.format(file['infile']))            
    run()
