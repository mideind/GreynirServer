import json
import logging
import datetime
from typing import cast

from query import Query, QueryStateDict
from tree import Result, Node, TerminalNode
from queries import gen_answer, parse_num
from queries.dialogue import (
    DatetimeResource,
    Resource,
    ResourceState,
    DialogueStateManager,
)

# Indicate that this module wants to handle parse trees for queries,
# as opposed to simple literal text strings
HANDLE_TREE = True

# The grammar nonterminals this module wants to handle
QUERY_NONTERMINALS = {"QFruitSeller"}

# The context-free grammar for the queries recognized by this plug-in module
GRAMMAR = """

Query →
    QFruitSeller '?'?

QFruitSeller →
    QFruitStartQuery | QFruitQuery | QFruitDateQuery

QFruitStartQuery →
    "ávöxtur"
    | "ég" "vill" "kaupa"? "ávexti"
    | "ég" "vil" "kaupa"? "ávexti"
    | "mig" "langar" "að" "kaupa" "ávexti" "hjá"? "þér"?
    | "mig" "langar" "að" "panta" "ávexti" "hjá"? "þér"?
    | "get" "ég" "keypt" "ávexti" "hjá" "þér"

QFruitQuery →
    QAddFruitQuery
    | QRemoveFruitQuery
    | QChangeFruitQuery
    | QFruitOptionsQuery
    | QYes
    | QNo
    | QCancelOrder

QAddFruitQuery →
    "já"? "má"? "ég"? "fá"? QFruitList
    | "já"? "get" "ég" "fengið" QFruitList
    | "já"? "gæti" "ég" "fengið" QFruitList
    | "já"? "ég" "vil" "fá" QFruitList
    | "já"? "ég" "vill" "fá" QFruitList
    | "já"? "ég" "vil" "panta" QFruitList
    | "já"? "ég" "vill" "panta" QFruitList
    | "já"? "ég" "vil" "kaupa" QFruitList
    | "já"? "ég" "vill" "kaupa" QFruitList
    | "já"? "mig" "langar" "að" "fá" QFruitList
    | "já"? "mig" "langar" "að" "kaupa" QFruitList
    | "já"? "mig" "langar" "að" "panta" QFruitList

QRemoveFruitQuery →
    "taktu" "út" QFruitList
    | "slepptu" QFruitList
    | "ég" "vil" "sleppa" QFruitList
    | "ég" "vill" "sleppa" QFruitList
    | "ég" "hætti" "við" QFruitList
    | "ég" "vil" "ekki" QFruitList
    | "ég" "vill" "ekki" QFruitList

QChangeFruitQuery →
    QChangeStart QFruitList QChangeConnector QFruitList

QChangeStart →
    "breyttu"
    | "ég" "vil" "frekar"
    | "ég" "vill" "frekar"
    | "ég" "vil" "skipta" "út"
    | "ég" "vill" "skipta" "út"
    | "ég" "vil" "breyta"
    | "ég" "vill" "breyta"

QChangeConnector →
    "en" | "í" "staðinn" "fyrir"

QFruitOptionsQuery →
    "hvað" "er" "í" "boði"
    | "hverjir" "eru" "valmöguleikarnir"
    | "hvaða" "valmöguleikar" "eru" "í" "boði" 
    | "hvaða" "valmöguleikar" "eru" "til"
    | "hvaða" "ávexti" "ertu" "með"
    | "hvaða" "ávextir" "eru" "í" "boði"

QFruitList → QNumOfFruit QNumOfFruit*

QNumOfFruit → QNum? QFruit "og"?

QNum →
    # to is a declinable number word ('tveir/tvo/tveim/tveggja')
    # töl is an undeclinable number word ('sautján')
    # tala is a number ('17')
    to | töl | tala

QFruit → 'banani' | 'epli' | 'pera' | 'appelsína'

QYes → "já" | "já" "takk" | "já" "þakka" "þér" "fyrir" | "já" "takk" "kærlega" "fyrir"?

QNo → "nei" | "nei" "takk"

QCancelOrder → "ég" "hætti" "við" 
    | "ég" "vil" "hætta" "við" "pöntunina"
    | "ég" "vill" "hætta" "við" "pöntunina" 

QFruitDateQuery →
    QFruitDateTime
    | QFruitDate
    | QFruitTime

QFruitDateTime →
    tímapunkturafs

QFruitDate →
    dagsafs
    | dagsföst

QFruitTime →
    "klukkan"? tími

"""

_START_DIALOGUE_QTYPE = "QFruitStartQuery"
_DIALOGUE_NAME = "fruitseller"


def QFruitStartQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = _START_DIALOGUE_QTYPE


def QAddFruitQuery(node: Node, params: QueryStateDict, result: Result):
    if "callbacks" not in result:
        result["callbacks"] = []
    result.callbacks.append(_add_fruit)
    result.qtype = "QAddFruitQuery"


def QRemoveFruitQuery(node: Node, params: QueryStateDict, result: Result):
    if "callbacks" not in result:
        result["callbacks"] = []
    result.callbacks.append(_remove_fruit)
    result.qtype = "QRemoveFruitQuery"


def QCancelOrder(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QCancelOrder"


def QFruitOptionsQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QFruitOptionsQuery"


def QYes(node: Node, params: QueryStateDict, result: Result):
    if "callbacks" not in result:
        result["callbacks"] = []
    result.callbacks.append(_parse_yes)
    result.qtype = "QYes"


def QNo(node: Node, params: QueryStateDict, result: Result):
    if "callbacks" not in result:
        result["callbacks"] = []
    result.callbacks.append(_parse_no)
    result.qtype = "QNo"


def QNumOfFruit(node: Node, params: QueryStateDict, result: Result):
    if "queryfruits" not in result:
        result["queryfruits"] = []
    if "fruitnumber" not in result:
        result.queryfruits.append([1, result.fruit])
    else:
        result.queryfruits.append([result.fruitnumber, result.fruit])


def QNum(node: Node, params: QueryStateDict, result: Result):
    fruitnumber = int(parse_num(node, result._nominative))
    if fruitnumber is not None:
        result.fruitnumber = fruitnumber
    else:
        result.fruitnumber = 1


def QFruit(node: Node, params: QueryStateDict, result: Result):
    fruit = result._root
    if fruit is not None:
        result.fruit = fruit


def QFruitDateTime(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "bull"
    datetimenode = node.first_child(lambda n: True)
    assert isinstance(datetimenode, TerminalNode)
    print(datetimenode.aux)
    now = datetime.datetime.now()
    y, m, d, h, min, _ = (i if i != 0 else None for i in json.loads(datetimenode.aux))
    if y is None:
        y = now.year
    if m is None:
        m = now.month
    if d is None:
        d = now.day
    if h is None:
        h = 12
    if min is None:
        min = 0
    result["delivery_time"] = datetime.time(h, min)
    result["delivery_date"] = datetime.date(y, m, d)

    def _dt_callback(resource: DatetimeResource, result: Result) -> None:
        if resource.data is None:
            resource.data = []
        print("DATETIME SHOULD BE FULFILLED NOW")
        resource.data.append(result["delivery_date"])
        resource.data.append(result["delivery_time"])
        resource.state = ResourceState.FULFILLED

    if "callbacks" not in result:
        result["callbacks"] = []
    result.callbacks.append(_dt_callback)


def QFruitDate(node: Node, params: QueryStateDict, result: Result) -> None:
    result.qtype = "bull"
    datenode = node.first_child(lambda n: True)
    assert isinstance(datenode, TerminalNode)
    cdate = datenode.contained_date
    if cdate:
        y, m, d = cdate
        now = datetime.datetime.utcnow()

        # This is a date that contains at least month & mday
        if d and m:
            if not y:
                y = now.year
                # Bump year if month/day in the past
                if m < now.month or (m == now.month and d < now.day):
                    y += 1
            result["delivery_date"] = datetime.date(day=d, month=m, year=y)
            print("DELIVERY DATE:", result["delivery_date"])

            def _dt_callback(resource: DatetimeResource, result: Result) -> None:
                if resource.data is None:
                    resource.data = []

                resource.data.append(result["delivery_date"])
                if isinstance(resource.data[0], datetime.time):
                    resource.data.reverse()
                    resource.state = ResourceState.FULFILLED
                else:
                    resource.state = ResourceState.PARTIALLY_FULFILLED

            if "callbacks" not in result:
                result["callbacks"] = []
            result.callbacks.append(_dt_callback)
            return
    raise ValueError("No date in {0}".format(str(datenode)))


def QFruitTime(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "bull"
    # Extract time from time terminal nodes
    tnode = cast(TerminalNode, node.first_child(lambda n: n.has_t_base("tími")))
    if tnode:
        aux_str = tnode.aux.strip("[]")
        hour, minute, _ = (int(i) for i in aux_str.split(", "))

        result["delivery_time"] = datetime.time(hour, minute)
        print("TIME IS: ", result["delivery_time"])

        def _dt_callback(resource: DatetimeResource, result: Result) -> None:
            if resource.data is None:
                resource.data = []
            resource.data.append(result["delivery_time"])
            if isinstance(resource.data[0], datetime.date):
                resource.state = ResourceState.FULFILLED
            else:
                resource.state = ResourceState.PARTIALLY_FULFILLED

        if "callbacks" not in result:
            result["callbacks"] = []
        result.callbacks.append(_dt_callback)


def _remove_fruit(resource: Resource, result: Result) -> None:
    if resource.data is not None:
        for _, fruitname in result.queryfruits:
            for number, name in resource.data:
                if name == fruitname:
                    resource.data.remove([number, name])
                    break
    if len(resource.data) == 0:
        resource.state = ResourceState.UNFULFILLED
    else:
        resource.state = ResourceState.PARTIALLY_FULFILLED


def _add_fruit(resource: Resource, result: Result) -> None:
    if resource.data is None:
        resource.data = []
    for number, name in result.queryfruits:
        resource.data.append((number, name))
    resource.state = ResourceState.PARTIALLY_FULFILLED


def _parse_no(resource: Resource, result: Result) -> None:
    print("No callback")
    if resource.name == "Fruits":
        if resource.state == ResourceState.PARTIALLY_FULFILLED:
            print("State is PARTIALLY_FULFILLED")
            resource.state = ResourceState.FULFILLED
            print("State after setting to FULFILLED")
        elif resource.state == ResourceState.FULFILLED:
            print("State is FULFILLED")
            resource.state = ResourceState.PARTIALLY_FULFILLED
            print("State after setting to PARTIALLY_FULFILLED")


def _parse_yes(resource: Resource, result: Result) -> None:
    if resource.name == "Fruits":
        if resource.state == ResourceState.FULFILLED:
            resource.state = ResourceState.CONFIRMED
    if resource.name == "Date":
        print("CONFIRMING DATETIME...", resource)
        if resource.state == ResourceState.FULFILLED:
            print("CONFIRMING DATETIME... 2")
            resource.state = ResourceState.CONFIRMED
            print("DATETIME CONFIRMED")


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dsm = DialogueStateManager(_DIALOGUE_NAME, q, result)

    if dsm.not_in_dialogue(_START_DIALOGUE_QTYPE):
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return
    print("Fyrir dsm")
    dsm.setup_dialogue()
    print("Eftir dms")
    # Successfully matched a query type
    try:
        if result.qtype == _START_DIALOGUE_QTYPE:
            dsm.start_dialogue()

        ans = dsm.generate_answer(result)
        dsm.update_dialogue_state()
        print("woohoo")

        if result.qtype == "OrderComplete" or result.qtype == "CancelOrder":
            dsm.end_dialogue()

        q.set_answer(*gen_answer(ans))
        return
    except Exception as e:
        logging.warning(
            "Exception {0} while processing fruit seller query '{1}'".format(e, q.query)
        )
        q.set_error("E_EXCEPTION: {0}".format(e))
