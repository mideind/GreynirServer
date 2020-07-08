




from queries import read_jsfile




user_data = {}




def handle_plain_text(q):
    """ Handle a plain text query, contained in the q parameter
        which is an instance of the query.Query class.
        Returns True if the query was handled, and in that case
        the appropriate properties on the Query instance have
        been set, such as the answer and the query type (qtype).
        If the query is not recognized, returns False. """
    ql = q.query_lower.rstrip('?')

    if ql == 'tengdu snjalltæki':
        q.set_qtype("Home")
        answer = 'Skal gert'

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("connectHub.js")

        q.set_command(js)

    if ql == "kveiktu ljós":

        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("light.js")
        js += 'main(true);'

        print(js)

        q.set_command(js)

    elif ql == 'slökktu ljós':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("light.js")
        js += 'main(false);'

        print(js)

        q.set_command(js)

    elif ql == 'hvar er ljós númer eitt':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("selectLight.js")
        js += 'main(1);'

        print(js)

        q.set_command(js)

    elif ql == 'hækkaðu birtuna':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("brightness.js")
        print(js)

        q.set_command(js)

    elif ql == 'lækkaðu birtuna':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("lowerbrightness.js")
        print(js)

        q.set_command(js)

    elif ql == 'hvítt ljós':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("color.js")
        print(js)

        q.set_command(js)
    
    elif ql == 'ég vil diskó':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("disco.js")
        print(js)

        q.set_command(js)

    elif ql == 'ég vil disco':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("disco.js")
        print(js)

        q.set_command(js)
    
    elif ql == 'prófaðu':
        q.set_qtype("Home")

        # A non-voice answer is usually a dict or a list
        answer = "Skal gert"

        q.set_answer(dict(answer=answer), answer, answer)

        js = read_jsfile("test.js")
        print(js)

        q.set_command(js)


    return True
