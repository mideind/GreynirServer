from typing import Any


class Resource:
    def __init__(self, required: bool = False):
        self.required = required
        self.data: Any = None
        self.partiallyFulfilled: bool = False
        self.fulfilled: bool = False
        self.state = None

    def isRequired(self) -> bool:
        return self.required

    def getData(self) -> Any:
        return self.data

    def isFulfilled(self) -> bool:
        return self.fulfilled

    def setData(self, data: Any):
        self.data = data

    def setFulfilled(self, fulfilled: bool):
        self.fulfilled = fulfilled


""" Three classes implemented for each resource
    class DataState():
        pass

    class PartiallyFulfilledState():
        pass

    class FulfillState(DataState):
        pass
"""
