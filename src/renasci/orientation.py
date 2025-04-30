from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class Gender(Enum):
    MALE = "Male"
    FEMALE = "Female"

    def get_opposite(self):
        return Gender.MALE if self == Gender.FEMALE else Gender.FEMALE
    
    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.vaule

    def __lt__(self, other: Gender) -> bool:
        return self.value < other.value
    
@dataclass
class Sexuality:
    value: Literal["Heterosexual", "Homosexual", "Bisexual", "Asexual"] = "Heterosexual" # TODO: should i just make this an enum?

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value

    def is_compatible(self, person1_gender: Gender, person2_gender: Gender) -> bool:
        if self.value == "Asexual":
            return False
        if self.value == "Heterosexual":
            return person1_gender != person2_gender
        if self.value == "Homosexual":
            return person1_gender == person2_gender
        if self.value == "Bisexual":
            return True
        return False