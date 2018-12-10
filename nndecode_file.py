"""
    Usage:
        NN_PARSING_ENABLED=1 \
        NN_PARSING_HOST=$PHOST \
        NN_PARSING_PORT=$PPORT \
        python nnclient.py \
        -i=source.txt -o=outputs.txt \
        -t=parse -b=80 --batch_by=lines

NN_PARSING_ENABLED=1 NN_PARSING_HOST=$BIRTA NN_PARSING_PORT=8180 \
python nnclient_file.py -i=/tmp/nnclient_file/test.batches.is -o=test.outputs.txt -t=parse -b=80 --batch_by=lines
"""


import logging
import os
import subprocess
import time

from nnclient import ParsingClient, TranslateClient


_logging_info_fn = print
_RETRY_WAIT_TIME = 10 # seconds
_MAX_RETRIES_IN_ROW = 3
_DEFAULT_BATCH_SIZE_LINES = 80


def get_completed(path):
    if not os.path.isfile(path):
        return set()
    ids = []
    with open(path, "r") as f:
        for entry in f:
            idx, line = entry.split("\t", 1)
            ids.append(int(idx))
    return set(ids)


def batch_by_lines(lines, completed, batch_size_in_lines):
    batch = []
    for (idx, line) in enumerate(lines):
        if idx in completed:
            continue
        line = line.strip("\n")
        batch.append((idx, line))
        if len(batch) >= batch_size_in_lines:
            yield batch
            batch = []
    if len(batch) > 0:
        yield batch


def batch_by_chars(lines, completed, batch_size_in_chars):
    batch = []
    accum_chars = 0
    for (idx, line) in enumerate(lines):
        line = line.strip("\n")
        if idx in completed:
            continue
        if accum_chars + len(line) > batch_size_in_chars:
            batch.append((idx, line))
            yield batch
            batch = []
            accum_chars = 0
    if len(batch) > 0:
        yield batch


def translate_file(in_path, out_path, verb, batch_size, batch_by):
    completed = get_completed(out_path)

    batch_gen = batch_by_lines if batch_by == "lines" else batch_by_chars

    _logging_info_fn("Translating {0}".format(in_path))
    _logging_info_fn("Output file is {0}".format(out_path))
    _logging_info_fn("Batch size is {0} {1}".format(batch_size, batch_by))
    _logging_info_fn("Currently {0} entries are done".format(len(completed)))

    with open(in_path, "r") as in_path:
        for (batch_num, batch) in enumerate(batch_gen(in_path, completed, batch_size)):
            begin_time = time.time()
            _logging_info_fn("Submitting batch {0}".format(batch_num))
            retries_in_row = 0
            while retries_in_row < _MAX_RETRIES_IN_ROW:
                try:
                    if retries_in_row > 0:
                        time.sleep(_RETRY_WAIT_TIME)
                        _logging_info_fn("Retrying...")
                    out_batch = translate_batch(batch, verb)
                    break
                except Exception as e:
                    logging.exception(e)
                    retries_in_row += 1
                    if retries_in_row >= _MAX_RETRIES_IN_ROW:
                        import traceback

                        traceback.print_exc()
                        _logging_info_fn("Maximum retries reached, exiting.")
                        return

            completed.update([entry[0] for entry in out_batch])
            with open(out_path, "a") as out_file:
                for (idx, outputs, scores) in out_batch:
                    msg = "{0}\t{1}\t{2}\n".format(idx, outputs, scores)
                    out_file.write(msg)
                elaps = round(time.time() - begin_time, 4)
                ms_per_example = round(100 * elaps / batch_size, 4)
                _logging_info_fn(
                    "Finished batch {0} in {1} seconds, {2} ms per example".format(
                        batch_num, elaps, ms_per_example
                    )
                )
    _logging_info_fn("Finished all batches")


def translate_batch(batch, verb):
    ids, sents = zip(*batch)
    client = (ParsingClient if verb == "parse"
              else TranslateClient)
    result = client._request(sents)

    out_batch = []
    for idx, inst in zip(ids, result):
        outputs = inst["outputs"]
        scores = inst["scores"]
        out_batch.append((idx, outputs, scores))
    return out_batch


def main(in_path, out_path, verb, batch_size, batch_by):
    translate_file(in_path, out_path, verb, batch_size, batch_by)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        "Translate a file by sending incremental batches to a tensorflow model server "
    )

    parser.add_argument(
        "-i",
        dest="IN_FILE",
        type=str,
        required=True,
        help="File that contains the source text to be translated",
    )
    parser.add_argument(
        "-o",
        dest="OUT_FILE",
        type=str,
        required=True,
        help="File that will contain the output of the translation system",
    )
    parser.add_argument(
        "-t",
        dest="VERB",
        choices=["parse", "translate"],
        type=str,
        required=True,
        help="Type of translation task to be performed",
    )
    parser.add_argument(
        "-b",
        dest="BATCH_SIZE",
        default=_DEFAULT_BATCH_SIZE_LINES,
        type=int,
        required=False,
        help="Batch size, default is {0} lines".format(_DEFAULT_BATCH_SIZE_LINES),
    )
    parser.add_argument(
        "--batch_by",
        dest="BATCH_BY",
        choices=["chars", "lines"],
        default="lines",
        type=str,
        required=True,
        help="Set which unit to batch by, defaults to line count.",
    )

    args = parser.parse_args()

    main(args.IN_FILE, args.OUT_FILE, args.VERB, args.BATCH_SIZE, args.BATCH_BY)
