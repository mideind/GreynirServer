from typing import Any, Optional, List

import pickle
import base64

from tree import Result
from queries.fruit_seller.resource import ListResource, Resource, ResourceState
from reynir import NounPhrase
from queries import natlang_seq, sing_or_plur, load_yaml_file


def _list_items(items: Any) -> str:
    item_list: List[str] = []
    for name in items.keys():
        number: int = items[name]
        # TODO: get general plural form
        plural_name: str = NounPhrase(name).dative or name
        item_list.append(sing_or_plur(number, name, plural_name))
    return natlang_seq(item_list)


class DialogueStateManager:
    def __init__(self):
        self.resources: List[Resource] = []
        self.resourceState: Optional[Resource] = None
        self.ans: Optional[str] = None

    def initialize_resources(self, dialogue: str) -> None:
        # Order here is the priority of each resource
        obj = load_yaml_file("fruit_seller/fruitseller.yaml")
        # print(obj["resources"])
        # TODO: parse yaml, add resources from yaml file

        self.resources.append(FruitState(prompt="Hvaða ávexti má bjóða þér?"))
        self.resources.append(OrderReceivedState())
        self.updateState(dialogue)

    def generateAnswer(self, type: str) -> None:
        # TODO: Move answers into each state and get the answer here
        if type == "QFruitStartQuery":
            self.ans = "Hvaða ávexti má bjóða þér?"
        elif type == "ListFruit":
            if self.resourceState is not None:
                if len(self.resourceState.data) != 0:
                    self.ans = "Komið! Pöntunin samanstendur af "
                    self.ans += _list_items(self.resourceState.data)
                    self.ans += ". Var það eitthvað fleira?"
                else:
                    self.ans = "Komið! Karfan er núna tóm. Hvaða ávexti má bjóða þér?"
            else:
                self.ans = "Kom upp villa, reyndu aftur."

        elif type == "FruitOrderNotFinished":
            self.ans = "Hverju viltu að bæta við pöntunina?"
        elif type == "FruitsFulfilled":
            self.ans = "Frábært! Á ég að staðfesta pöntunina?"
        elif type == "FruitMethodNotFound":
            self.ans = "Ég get ekki tekið við þessari beiðni strax."
        elif type == "OrderComplete":
            self.ans = "Frábært, pöntunin er staðfest!"
        elif type == "OrderWrong":
            self.ans = "Leitt að heyra, viltu hætta við pöntunina eða breyta henni?"
        elif type == "CancelOrder":
            self.ans = "Móttekið. Hætti við pöntunina."
        elif type == "FruitOptions":
            self.ans = "Hægt er að panta appelsínur, banana, epli og perur."
        elif type == "FruitRemoved":
            self.ans = "Karfan hefur verið uppfærð. Var það eitthvað fleira?"
        elif type == "NoFruitMatched":
            self.ans = "Enginn ávöxtur í körfunni passaði við beiðnina á undan."
        elif type == "NoFruitToRemove":
            self.ans = "Engir ávextir eru í körfunni til að fjarlægja."

    def updateState(self, type: str) -> None:
        for resource in self.resources:
            if resource.required and resource.state is not ResourceState.FULFILLED:
                if resource.data is None:
                    if self.resourceState is not resource:
                        self.resourceState = resource
                    resource.state = resource.DataState(
                        resource.data, resource.partiallyFulfilled, resource.fulfilled
                    )
                    break
                elif not resource.partiallyFulfilled:
                    resource.state = resource.PartiallyFulfilledState(
                        resource.data, resource.partiallyFulfilled, resource.fulfilled
                    )
                    break
                elif resource.partiallyFulfilled:
                    resource.state = resource.FulfilledState(
                        resource.data, resource.partiallyFulfilled, resource.fulfilled
                    )
                    break
        self.generateAnswer(type)
        print("Current state: ", self.resourceState.state)

    def stateMethod(self, methodName: str, result: Result):
        try:
            if self.resourceState is not None:
                method = getattr(self.resourceState.state, methodName)
                if method is not None:
                    (
                        self.resourceState.data,
                        self.resourceState.partiallyFulfilled,
                        self.resourceState.fulfilled,
                    ) = method(result)
                self.updateState(result.qtype)
            else:
                self.ans = "Kom upp villa, reyndu aftur."
        except Exception as e:
            print("Error: ", e)
            result.qtype = "FruitMethodNotFound"

    @classmethod
    def serialize(cls, instance: "DialogueStateManager") -> str:
        return base64.b64encode(pickle.dumps(instance)).decode("utf-8")

    @classmethod
    def deserialize(cls, serialized: str) -> "DialogueStateManager":
        return pickle.loads(base64.b64decode(serialized.encode("utf-8")))


class FruitState(ListResource):
    # def generate_answer

    class DataState:
        def __init__(self, data: Any, partiallyFulfilled: bool, fulfilled: bool):
            self.data = data
            self.partiallyFulfilled = partiallyFulfilled
            self.fulfilled = fulfilled

        # Add fruits to array and switch to OrderReceived state
        def QAddFruitQuery(self, result: Result):
            if self.data is None:
                self.data = result.queryfruits
            else:
                for fruitname in result.queryfruits.keys():
                    self.data[fruitname] = result.queryfruits[fruitname]
            result.fruits = self.data
            result.qtype = "ListFruit"
            return (self.data, self.partiallyFulfilled, self.fulfilled)

        # Remove fruits from array
        def QRemoveFruitQuery(self, result: Result):
            result.qtype = ""
            if self.data is None:
                result.qtype = "NoFruitToRemove"
            else:
                for fruitname in result.queryfruits.keys():
                    removedValue = self.data.pop(fruitname, "NoFruitMatched")
                    if removedValue == "NoFruitMatched":
                        result.qtype = "NoFruitMatched"
                if result.qtype != "NoFruitMatched":
                    result.qtype = "ListFruit"
                    result.fruits = self.data
            return (self.data, self.partiallyFulfilled, self.fulfilled)

        # Change the fruits array
        def QChangeFruitQuery(self, result: Result):
            pass

        # Inform what fruits are available
        def QFruitOptionsQuery(self, result: Result):
            result.qtype = "FruitOptions"
            return (self.data, self.partiallyFulfilled, self.fulfilled)

        # User wants to stop conversation
        def QCancelOrder(self, result: Result):
            result.qtype = "CancelOrder"
            return (self.data, self.partiallyFulfilled, self.fulfilled)

    class PartiallyFulfilledState(DataState):
        def __init__(self, data: Any, partiallyFulfilled: bool, fulfilled: bool):
            super().__init__(data, partiallyFulfilled, fulfilled)

        # User is happy with the order, switch to confirm state
        def QNo(self, result: Result):
            result.qtype = "FruitsFulfilled"
            self.partiallyFulfilled = True
            return (self.data, self.partiallyFulfilled, self.fulfilled)

        # User wants to add more to the order, ask what
        def QYes(self, result: Result):
            result.qtype = "FruitOrderNotFinished"
            return (self.data, self.partiallyFulfilled, self.fulfilled)

    class FulfilledState(DataState):
        def __init__(self, data: Any, partiallyFulfilled: bool, fulfilled: bool):
            super().__init__(data, partiallyFulfilled, fulfilled)

        # The order is correct, say the order is confirmed
        def QYes(self, result: Result):
            result.qtype = "OrderComplete"
            self.fulfilled = True
            return (self.data, self.partiallyFulfilled, self.fulfilled)

        # Order was wrong, ask the user to start again
        def QNo(self, result: Result):
            result.qtype = "OrderWrong"
            self.partiallyFulfilled = False
            return (self.data, self.partiallyFulfilled, self.fulfilled)


class OrderReceivedState(FruitState):
    def __init__(self, required: bool = True):
        super().__init__(required)

    # User is happy with the order, switch to confirm state
    def QNo(self, result: Result):
        result.qtype = "FruitsFulfilled"
        self.fulfilled = True
        return ConfirmOrderState(self.fruits, self.date)

    # User wants to add more to the order, ask what
    def QYes(self, result: Result):
        result.qtype = "FruitOrderNotFinished"
        return FruitState(self.fruits, self.date)


class ConfirmOrderState(FruitState):
    def __init__(self, fruits, date):
        self.fruits = fruits
        self.date = date

    # The order is correct, say the order is confirmed
    def QYes(self, result: Result):
        result.qtype = "OrderComplete"

    # Order was wrong, ask the user to start again
    def QNo(self, result: Result):
        result.qtype = "OrderWrong"
        self.fruits.fulfilled = False
        return FruitState(self.fruits, self.date)
