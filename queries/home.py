




from queries import read_jsfile









def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip('?')


    if ql == "kveiktu ljós":

        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("test.js")

        q.set_command(js)


    return True
