from typing import Any, Optional, List

from tree import Result
from queries.fruit_seller.resource import Resource
from reynir import NounPhrase


class FruitStateManager:
    def __init__(self):
        self.resources: List[Resource] = []
        self.fruitState: Optional[Resource] = None
        self.ans: Optional[str] = None

    def startFruitOrder(self) -> None:
        # Order here is the priority of each resource
        self.resources.append(FruitState(required=True))
        self.resources.append(OrderReceivedState(required=True))
        self.updateState("FruitStart")

    def generateAnswer(self, type: str) -> None:
        if type == "FruitStart":
            self.ans = "Hvaða ávexti má bjóða þér?"
        elif type == "ListFruit":
            if self.fruitState is not None:
                if len(self.fruitState.data) != 0:
                    self.ans = "Komið! Pöntunin samanstendur af "
                    for fruitname in self.fruitState.data.keys():
                        fruitNumber = self.fruitState.data[fruitname]
                        if fruitname == "banani":
                            self.ans += (
                                "banana "
                                if (fruitNumber == 1)
                                else f"{fruitNumber} bönunum "
                            )
                        elif fruitname == "appelsína":
                            self.ans += (
                                "appelsínu "
                                if (fruitNumber == 1)
                                else f"{fruitNumber} appelsínum "
                            )
                        elif fruitname == "pera":
                            self.ans += (
                                "peru " if (fruitNumber == 1) else f"{fruitNumber} perum "
                            )
                        elif fruitname == "epli":
                            self.ans += (
                                "epli " if (fruitNumber == 1) else f"{fruitNumber} eplum "
                            )
                        else:
                            self.ans += f"{'' if (fruitNumber == 1) else f'{fruitNumber} '}{NounPhrase(fruitname).dative} "
                    self.ans = self.ans.rstrip() + ". Var það eitthvað fleira?"
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
            if resource.required and not resource.fulfilled:
                if resource.data is None:
                    if self.fruitState is not resource:
                        self.fruitState = resource
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
        print("Current state: ", self.fruitState.state)

    def stateMethod(self, methodName: str, result: Result):
        try:
            if self.fruitState is not None:
                method = getattr(self.fruitState.state, methodName)
                if method is not None:
                    (
                        self.fruitState.data,
                        self.fruitState.partiallyFulfilled,
                        self.fruitState.fulfilled,
                    ) = method(result)
                self.updateState(result.qtype)
            else:
                self.ans = "Kom upp villa, reyndu aftur."
        except Exception as e:
            print("Error: ", e)
            result.qtype = "FruitMethodNotFound"


class FruitState(Resource):
    def __init__(self, required: bool = True):
        super().__init__(required)

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
