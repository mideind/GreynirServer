import logging

from query import Query, QueryStateDict
from tree import Result, Node
from queries import gen_answer, parse_num
from queries.fruit_seller.fruitstate import DialogueStateManager
from queries.fruit_seller.resource import Resource, ResourceState

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
    QFruitStartQuery | QFruitQuery

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

"""

_START_CONVERSATION_QTYPE = "QFruitStartQuery"
_DIALOGUE_NAME = "fruitseller"


def QFruitStartQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = _START_CONVERSATION_QTYPE


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
    result.qtype = "QYes"


def QNo(node: Node, params: QueryStateDict, result: Result):
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


def _remove_fruit(resource: Resource, result: Result) -> None:
    if resource.data is not None:
        for _, fruitname in result.queryfruits:
            for number, name in resource.data:
                if name == fruitname:
                    resource.data.remove([number, name])
                    break


def _add_fruit(resource: Resource, result: Result) -> None:
    if resource.data is None:
        resource.data = []
    for number, name in result.queryfruits:
        resource.data.append((number, name))
    resource.state = ResourceState.PARTIALLY_FULFILLED


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dialogue_state = q.get_dialogue_state() or {}
    qt = result.get("qtype")

    print("Dialogue state: ", dialogue_state)
    # checka hvort user se i samtali med q.client_data
    if qt != _START_CONVERSATION_QTYPE and not (
        dialogue_state and dialogue_state.get("dialogue_name") == _DIALOGUE_NAME
    ):
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return
    print("Fyrir dsm")
    dsm = DialogueStateManager("fruit_seller/fruitseller.yaml", q.get_dialogue_state())
    print("Eftir dms")
    # Successfully matched a query type
    try:
        if result.qtype == _START_CONVERSATION_QTYPE:
            q.set_dialogue_state(
                {"dialogue_name": "fruitseller", "resources": [], "variables": None}
            )
        else:
            print("Í else")
            if dialogue_state is None:
                q.set_error("E_QUERY_NOT_UNDERSTOOD")
                return
        print("fyrir generate")
        ans = dsm.generate_answer(result)
        print("eftir generate")
        q.set_dialogue_state(
            {
                "dialogue_name": "fruitseller",
                "resources": [r.__dict__ for r in dsm.resources],
                "variables": None,
            }
        )
        print("woohoo")

        if result.qtype == "OrderComplete" or result.qtype == "CancelOrder":
            q.end_dialogue()

        q.set_answer(*gen_answer(ans))
        return
    except Exception as e:
        logging.warning(
            "Exception {0} while processing fruit seller query '{1}'".format(e, q.query)
        )
        q.set_error("E_EXCEPTION: {0}".format(e))
