from queries.dialogue import (
    ListResource,
)

class FruitResource(ListResource):
    def generate_answer(self) -> str:
        ans = super().generate_answer()
        """ans: str = ""
        if type == "QFruitStartQuery":
            ans = "Hvaða ávexti má bjóða þér?"
        elif type == "ListFruit":
            if len(self.data) != 0:
                ans = "Komið! Pöntunin samanstendur af "
                ans += list_items(self.data)
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
            ans = "Engir ávextir eru í körfunni til að fjarlægja." """
        return ans
