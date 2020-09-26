# -*- coding: utf-8 -*-

"""

Sort utility for large UTF-8 text files

Adapted from Recipe 466302: Sorting big files the Python 2.4 way
    by Nicolas Lehuen
    http://code.activestate.com/recipes/576755-sorting-big-files-the-python-26-way/

Example usage:

python sortfile.py resources/ordalisti.txt resources/ordalisti.sorted.txt -b 200000

"""

import os
import io
from tempfile import gettempdir
from itertools import islice, cycle
from collections import namedtuple
import heapq

Keyed = namedtuple("Keyed", ["key", "obj"])

def keyfunc(line):
    return line

def merge(*iterables):
    # based on code posted by Scott David Daniels in c.l.p.
    # http://groups.google.com/group/comp.lang.python/msg/484f01f1ea3c832d

    keyed_iterables = [
        (Keyed(keyfunc(obj), obj)
        for obj in iterable)
        for iterable in iterables]
    for element in heapq.merge(*keyed_iterables):
        yield element.obj


def batch_sort(infile, output, buffer_size=32000, tempdirs=None):
    if tempdirs is None:
        tempdirs = []
    if not tempdirs:
        tempdirs.append(gettempdir())

    chunks = []
    try:
        with io.open(infile, mode='r', buffering=64*1024, encoding='utf8') as input_file:
            print(u"Opened input {0}".format(infile))
            input_iterator = iter(input_file)
            for tempdir in cycle(tempdirs):
                current_chunk = list(islice(input_iterator,buffer_size))
                if not current_chunk:
                    break
                current_chunk.sort(key=keyfunc)
                fname = '%06i' % len(chunks)
                output_chunk = io.open(os.path.join(tempdir,fname),mode='w+',buffering=64*1024, encoding='utf8')
                print(u"Writing tempfile {0}/{1}".format(tempdir, fname))
                chunks.append(output_chunk)
                output_chunk.writelines(current_chunk)
                output_chunk.flush()
                output_chunk.seek(0)
        print(u"Writing outfile {0}".format(output))
        with io.open(output,mode='w',buffering=64*1024, encoding='utf8') as output_file:
            output_file.writelines(merge(*chunks))
    finally:
        for chunk in chunks:
            # noinspection PyBroadException
            try:
                chunk.close()
                os.remove(chunk.name)
            except:
                print(u"Exception when closing chunk")
                pass


if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser()
    parser.add_option(
        '-b','--buffer',
        dest='buffer_size',
        type='int',default=32000,
        help='''Size of the line buffer. The file to sort is
            divided into chunks of that many lines. Default : 32,000 lines.'''
    )
    parser.add_option(
        '-t','--tempdir',
        dest='tempdirs',
        action='append',
        default=[],
        help='''Temporary directory to use. You might get performance
            improvements if the temporary directory is not on the same physical
            disk than the input and output directories. You can even try
            providing multiples directories on differents physical disks.
            Use multiple -t options to do that.'''
    )
    options,args = parser.parse_args()

    batch_sort(args[0],args[1],options.buffer_size,options.tempdirs)
