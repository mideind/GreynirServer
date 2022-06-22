from typing import Any


class Resource:
    def __init__(self, required: bool = False):
        self.required = required
        self.data: Any = None
        self.partiallyFulfilled: bool = False
        self.fulfilled: bool = False
        self.state = None

    def generate_answer(self, type: str) -> str:
        return ""


""" Three classes implemented for each resource
    class DataState():
        pass

    class PartiallyFulfilledState():
        pass

    class FulfillState(DataState):
        pass
"""
