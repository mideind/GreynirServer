from typing import Any, Callable, List, Optional, cast
import json
import logging
import datetime

from query import Query, QueryStateDict
from tree import Result, Node, TerminalNode
from reynir import NounPhrase
from queries import gen_answer, parse_num, natlang_seq, sing_or_plur
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
    QFruitStartQuery
    | QFruitQuery
    | QFruitDateQuery

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
    | "ég"? "vil"? "sleppa" QFruitList
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

QYes → "já" "já"* | "já" "takk" | "játakk" | "já" "þakka" "þér" "fyrir" | "já" "takk" "kærlega" "fyrir"? | "jább" "takk"?

QNo → "nei" "takk"? | "nei" "nei"* | "neitakk"

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

def _generate_fruit_answer(resource: Resource, dsm: DialogueStateManager) -> Optional[str]:
    ans: Optional[str] = None
    if dsm.get_result()["fruitsEmpty"]:
        ans = resource.prompts["empty"]
    elif dsm.get_result()["fruitOptions"]:
        ans = resource.prompts["options"]
    if resource.state is ResourceState.CONFIRMED:
        return None
    if resource.state is ResourceState.UNFULFILLED:
        ans = resource.prompts["initial"]
    elif resource.state is ResourceState.PARTIALLY_FULFILLED:
        ans = (
            f"{resource.prompts['repeat'].format(list_items = _list_items(resource.data))}"
        )
    elif resource.state is ResourceState.FULFILLED:
        ans = (
            f"{resource.prompts['confirm'].format(list_items = _list_items(resource.data))}"
        )
    return ans

def _generate_date_answer(resource: DatetimeResource, dsm: DialogueStateManager) -> Optional[str]:
    ans: Optional[str] = None
    if resource.state is ResourceState.CONFIRMED:
        return None

    if resource.state is ResourceState.UNFULFILLED:
        ans = resource.prompts["initial"]

    elif resource.state is ResourceState.PARTIALLY_FULFILLED:
        if resource.has_date():
            ans = resource.prompts["date_fulfilled"].format(
                date = resource.data[0].strftime("%Y/%m/%d")
            )
        if resource.has_time() and resource.prompts["time_fulfilled"]:
            ans = resource.prompts["time_fulfilled"].format(
                time = resource.data[1].strftime("%H:%M")
            )

    elif resource.state is ResourceState.FULFILLED:
        if resource.has_date() and resource.has_time():
            ans = resource.prompts["confirm"].format(
                date_time=datetime.datetime.combine(
                    cast(datetime.date, resource.data[0]),
                    cast(datetime.time, resource.data[1]),
                ).strftime("%Y/%m/%d %H:%M")
            )
    return ans

def _generate_final_answer(resource: Resource, dsm: DialogueStateManager) -> Optional[str]:
    ans: Optional[str] = None
    if resource.state is ResourceState.CONFIRMED:
        date_resource = dsm.get_resource("Date")
        ans = resource.prompts["final"].format(
            fruits = _list_items(dsm.get_resource("Fruits").data),
            date_time = datetime.datetime.combine(
                        cast(datetime.date, date_resource.data[0]),
                        cast(datetime.time, date_resource.data[1]),
                    ).strftime("%Y/%m/%d %H:%M")
        )
    elif resource.state is ResourceState.CANCELLED:
        ans = resource.prompts["cancelled"]
    return ans

def _list_items(items: Any) -> str:
    item_list: List[str] = []
    for num, name in items:
        # TODO: get general plural form
        plural_name: str = NounPhrase(name).dative or name
        item_list.append(sing_or_plur(num, name, plural_name))
    return natlang_seq(item_list)


def QFruitStartQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = _START_DIALOGUE_QTYPE
    result.answer_key = ("Fruits", "initial")


def QAddFruitQuery(node: Node, params: QueryStateDict, result: Result):
    def _add_fruit(resource: Resource, result: Result) -> None:
        if resource.data is None:
            resource.data = []
        for number, name in result.queryfruits:
            resource.data.append((number, name))
        resource.state = ResourceState.PARTIALLY_FULFILLED
        print("INSIDE ADD FRUITS CALLBACK", resource.name)
        resource.set_answer("repeat", list_items=_list_items(resource.data))
        print("ANSWER IS:", resource._answer)

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Fruits"
    result.callbacks.append((filter_func, _add_fruit))
    result.qtype = "QAddFruitQuery"


def QRemoveFruitQuery(node: Node, params: QueryStateDict, result: Result):
    def _remove_fruit(resource: Resource, result: Result) -> None:
        if resource.data is not None:
            for _, fruitname in result.queryfruits:
                for number, name in resource.data:
                    if name == fruitname:
                        resource.data.remove([number, name])
                        break
        if len(resource.data) == 0:
            resource.state = ResourceState.UNFULFILLED
            resource.set_answer("empty")
            result.fruitsEmpty = True
        else:
            resource.state = ResourceState.PARTIALLY_FULFILLED
            resource.set_answer("repeat", list_items=_list_items(resource.data))

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Fruits"
    result.callbacks.append((filter_func, _remove_fruit))
    result.qtype = "QRemoveFruitQuery"


def QCancelOrder(node: Node, params: QueryStateDict, result: Result):
    def _cancel_order(resource: Resource, result: Result) -> None:
        resource.state = ResourceState.CANCELLED
    result.qtype = "QCancelOrder"
    result.answer_key = ("Final", "cancelled")
    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Final"
    result.callbacks.append((filter_func, _cancel_order))


def QFruitOptionsQuery(node: Node, params: QueryStateDict, result: Result):
    result.qtype = "QFruitOptionsQuery"
    result.answer_key = ("Fruits", "options")
    result.fruitOptions = True


def QYes(node: Node, params: QueryStateDict, result: Result):
    def _parse_yes(resource: Resource, result: Result) -> None:
        if resource.name == "Fruits":
            if resource.is_fulfilled:
                resource.state = ResourceState.CONFIRMED
        if resource.name == "Date":
            if resource.is_fulfilled:
                resource.state = ResourceState.CONFIRMED
                result.answer_key = ("Final", "final")

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = (
        lambda r: r.name in ("Fruits", "Date") and not r.is_confirmed
    )
    result.callbacks.append((filter_func, _parse_yes))
    result.qtype = "QYes"


def QNo(node: Node, params: QueryStateDict, result: Result):
    def _parse_no(resource: Resource, result: Result) -> None:
        if resource.name == "Fruits":
            if resource.is_partially_fulfilled:
                resource.state = ResourceState.FULFILLED
                resource.set_answer("confirm", list_items=_list_items(resource.data))
            elif resource.is_fulfilled:
                resource.state = ResourceState.PARTIALLY_FULFILLED
                resource.set_answer("repeat", list_items=_list_items(resource.data))

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = (
        lambda r: r.name in ("Fruits", "Date") and not r.is_confirmed
    )
    result.callbacks.append((filter_func, _parse_no))
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
        resource.set_date(result["delivery_date"])
        resource.set_time(result["delivery_time"])
        resource.state = ResourceState.FULFILLED
        resource.set_answer(
            "confirm",
            date_time=datetime.datetime.combine(resource.date, resource.time).strftime(
                "%Y/%m/%d %H:%M"
            ),
        )

    if "callbacks" not in result:
        result["callbacks"] = []
    filter_func: Callable[[Resource], bool] = lambda r: r.name == "Date"
    result.callbacks.append((filter_func, _dt_callback))


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

            def _dt_callback(resource: DatetimeResource, result: Result) -> None:
                resource.set_date(result["delivery_date"])
                if resource.has_time():
                    resource.state = ResourceState.FULFILLED
                    resource.set_answer(
                        "confirm",
                        date_time=datetime.datetime.combine(
                            resource.date, resource.time
                        ).strftime("%Y/%m/%d %H:%M"),
                    )
                else:
                    resource.state = ResourceState.PARTIALLY_FULFILLED
                    resource.set_answer(
                        "date_fulfilled", date=resource.date.strftime("%Y/%m/%d")
                    )

            if "callbacks" not in result:
                result["callbacks"] = []
            filter_func: Callable[[Resource], bool] = lambda r: r.name == "Date"
            result.callbacks.append((filter_func, _dt_callback))
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

        def _dt_callback(resource: DatetimeResource, result: Result) -> None:
            resource.set_time(result["delivery_time"])
            if resource.has_date():
                resource.state = ResourceState.FULFILLED
                resource.set_answer(
                    "confirm",
                    date_time=datetime.datetime.combine(
                        resource.date, resource.time
                    ).strftime("%Y/%m/%d %H:%M"),
                )
            else:
                resource.state = ResourceState.PARTIALLY_FULFILLED
                resource.set_answer(
                    "time_fulfilled", time=resource.time.strftime("%H:%M")
                )

        if "callbacks" not in result:
            result["callbacks"] = []
        filter_func: Callable[[Resource], bool] = lambda r: r.name == "Date"
        result.callbacks.append((filter_func, _dt_callback))


def sentence(state: QueryStateDict, result: Result) -> None:
    """Called when sentence processing is complete"""
    q: Query = state["query"]
    dsm = DialogueStateManager(_DIALOGUE_NAME, _START_DIALOGUE_QTYPE, q, result)

    if dsm.not_in_dialogue():
        q.set_error("E_QUERY_NOT_UNDERSTOOD")
        return

    # Successfully matched a query type
    try:
        dsm.setup_dialogue()
        if result.qtype == _START_DIALOGUE_QTYPE:
            dsm.start_dialogue()

        ans = dsm.get_answer()
        if not ans:
            raise ValueError("No answer generated!")

        q.set_answer(*gen_answer(ans))
        return
    except Exception as e:
        logging.warning(
            "Exception {0} while processing fruit seller query '{1}'".format(e, q.query)
        )
        q.set_error("E_EXCEPTION: {0}".format(e))
