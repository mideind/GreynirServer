from typing import Any, Optional, List

import pickle
import base64

from tree import Result
from query import DialogueStructureType
from queries.fruit_seller.resource import (
    DatetimeResource,
    ListResource,
    Resource,
    ResourceState,
)
from reynir import NounPhrase
from queries import natlang_seq, sing_or_plur, load_dialogue_structure


def _list_items(items: Any) -> str:
    item_list: List[str] = []
    for name in items.keys():
        number: int = items[name]
        # TODO: get general plural form
        plural_name: str = NounPhrase(name).dative or name
        item_list.append(sing_or_plur(number, name, plural_name))
    return natlang_seq(item_list)


class DialogueStateManager:
    def __init__(
        self, yaml_file: str, saved_state: Optional[DialogueStructureType] = None
    ):
        obj = load_dialogue_structure(yaml_file)
        print(obj)
        self.resources: List[Resource] = []
        for i, resource in enumerate(obj["resources"]):
            newResource: Resource
            if resource.get("type") == "ListResource":
                newResource = ListResource(**resource)
            else:
                newResource = DatetimeResource(**resource)
            if saved_state and i < len(saved_state["resources"]):
                newResource.update(saved_state["resources"][i])
            self.resources.append(newResource)

        self.resourceState: Optional[Resource] = None
        self.ans: Optional[str] = None

    def generate_answer(self, result: Result) -> str:
        for resource in self.resources:
            if resource.required and resource.state is not ResourceState.CONFIRMED:
                if "callbacks" in result:
                    for cb in result.callbacks:
                        cb(resource, result)
                return resource.generate_answer()
        return "Upp kom villa, reyndu aftur."

    def updateState(self, type: str) -> None:
        for resource in self.resources:
            if resource.required and resource.state is not ResourceState.FULFILLED:
                if resource.data is None:
                    if self.resourceState is not resource:
                        self.resourceState = resource
                    resource.state = resource.DataState(resource.data)
                    break
                elif resource.state is not ResourceState.PARTIALLY_FULFILLED:
                    resource.state = resource.PartiallyFulfilledState(resource.data)
                    break
                elif resource.state is ResourceState.PARTIALLY_FULFILLED:
                    resource.state = resource.FulfilledState(resource.data)
                    break
        self.generate_answer(type)
        print("Current state: ", self.resourceState.state)

    def stateMethod(self, methodName: str, result: Result):
        try:
            if self.resourceState is not None:
                method = getattr(self.resourceState.state, methodName)
                if method is not None:
                    (self.resourceState.data, self.resourceState.state) = method(result)
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
    def generate_answer(self, type: str) -> str:
        ans: str = ""
        if type == "QFruitStartQuery":
            ans = "Hvaða ávexti má bjóða þér?"
        elif type == "ListFruit":
            if len(self.data) != 0:
                ans = "Komið! Pöntunin samanstendur af "
                ans += _list_items(self.data)
                ans += ". Var það eitthvað fleira?"
            else:
                ans = "Komið! Karfan er núna tóm. Hvaða ávexti má bjóða þér?"

        elif type == "FruitOrderNotFinished":
            ans = "Hverju viltu að bæta við pöntunina?"
        elif type == "FruitsFulfilled":
            ans = "Frábært! Á ég að staðfesta pöntunina?"
        elif type == "FruitMethodNotFound":
            self.ans = "Ég get ekki tekið við þessari beiðni strax."
        elif type == "OrderComplete":
            ans = "Frábært, pöntunin er staðfest!"
        elif type == "OrderWrong":
            ans = "Leitt að heyra, viltu hætta við pöntunina eða breyta henni?"
        elif type == "CancelOrder":
            ans = "Móttekið. Hætti við pöntunina."
        elif type == "FruitOptions":
            ans = "Hægt er að panta appelsínur, banana, epli og perur."
        elif type == "FruitRemoved":
            ans = "Karfan hefur verið uppfærð. Var það eitthvað fleira?"
        elif type == "NoFruitMatched":
            ans = "Enginn ávöxtur í körfunni passaði við beiðnina á undan."
        elif type == "NoFruitToRemove":
            ans = "Engir ávextir eru í körfunni til að fjarlægja."
        return ans

    class DataState:
        def __init__(self, data: Any):
            self.data = data

        # Add fruits to array and switch to OrderReceived state
        def QAddFruitQuery(self, result: Result):
            if self.data is None:
                self.data = result.queryfruits
            else:
                for fruitname in result.queryfruits.keys():
                    self.data[fruitname] = result.queryfruits[fruitname]
            result.fruits = self.data
            result.qtype = "ListFruit"
            return (self.data, ResourceState.PARTIALLY_FULFILLED)

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
            return (
                self.data,
                ResourceState.PARTIALLY_FULFILLED
                if len(self.data) != 0
                else ResourceState.UNFULFILLED,
            )

        # Change the fruits array
        def QChangeFruitQuery(self, result: Result):
            pass

        # Inform what fruits are available
        def QFruitOptionsQuery(self, result: Result):
            result.qtype = "FruitOptions"
            return (
                self.data,
                ResourceState.UNFULFILLED
                if self.data is None
                else ResourceState.PARTIALLY_FULFILLED,
            )

        # User wants to stop conversation
        def QCancelOrder(self, result: Result):
            result.qtype = "CancelOrder"
            return (self.data, ResourceState.UNFULFILLED)

    class PartiallyFulfilledState(DataState):
        def __init__(self, data: Any):
            super().__init__(data)

        # User is happy with the order, switch to confirm state
        def QNo(self, result: Result):
            result.qtype = "FruitsFulfilled"
            return (self.data, ResourceState.FULFILLED)

        # User wants to add more to the order, ask what
        def QYes(self, result: Result):
            result.qtype = "FruitOrderNotFinished"
            return (self.data, ResourceState.PARTIALLY_FULFILLED)

    class FulfilledState(DataState):
        def __init__(self, data: Any):
            super().__init__(data)

        # The order is correct, say the order is confirmed
        def QYes(self, result: Result):
            result.qtype = "OrderComplete"
            return (self.data, ResourceState.CONFIRMED)

        # Order was wrong, ask the user to start again
        def QNo(self, result: Result):
            result.qtype = "OrderWrong"
            return (self.data, ResourceState.FULFILLED)


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
