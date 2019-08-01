"""

    Reynir: Natural language processing for Icelandic

    Arithmetic query response module

    Copyright (C) 2019 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.

"""

from tokenizer import tokenize, TOK

_OPERATORS = {"sinnum": "*", "plús": "+", "mínus": "-", "deiltmeð": "/"}

# TODO: Ráða við töluorð
# TODO: Support "hvað er x í y veldi" and "hver er kvaðraðrótin af x"

def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower

    if not ql.startswith("hvað er "):
        return False

    ql = ql[8:]
    if ql.endswith("?"):
        ql = ql[:-1]

    ql = ql.replace("deilt með", "deiltmeð")

    tokens = list(tokenize(ql))[1:-1]
    # For now, we only support arithmetic queries of
    # the form "NUMBER OPERATOR NUMBER"
    if (
        len(tokens) != 3
        or tokens[0].kind != TOK.NUMBER
        or tokens[1].txt not in _OPERATORS.keys()
        or tokens[2].kind != TOK.NUMBER
    ):
        return False

    def proc(t):
        if t.txt in _OPERATORS.keys():
            return _OPERATORS[t.txt]
        if t.kind == TOK.NUMBER:
            return str(t.val[0])
        return ""

    qs = " ".join([proc(t) for t in tokens])
    # EVAL!!!
    result = eval(qs, {"__builtins__": None}, {})

    if isinstance(result, float):
        answer = "{0:.2f}".format(result).replace(".", ",")
        while answer.endswith("0") or answer.endswith(","):
            answer = answer[:-1]
    else:
        answer = str(result)

    q.set_qtype("Arithmetic")
    response = dict(answer=answer)
    voice = "{0} er {1}".format(ql, answer)
    q.set_answer(response, answer, voice)

    return True
