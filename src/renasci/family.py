from __future__ import annotations
from dataclasses import dataclass, field

from renasci.orientation import Gender

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.person import Person, PersonView
    from renasci.house import House

@dataclass
class Family:
    mother: Person | None = None
    father: Person | None = None
    children: list[Person] = field(default_factory=list)

    def add_child(self, child: Person):
        self.children.append(child)

    def get_living_children(self,):
        return [child for child in self.children if child.is_alive]
    
    def get_children_age_sorted(self, reverse : bool = False):
        return sorted(self.children, key=lambda p: p.life.birth_year, reverse=reverse)

    def siblings(self) -> list[Person]:
        siblings = []
        if self.mother:
            siblings.extend(self.mother.family.children)
        if self.father:
            siblings.extend(self.father.family.children)
        # Remove duplicates and self
        return list({s for s in siblings if s != self})
    
    def is_child_of(self, parent : Person) -> bool:
        return parent in (self.father, self.mother)
    

@dataclass
class Marriage:
    partner1: Person
    partner2: Person
    year_of_marriage: int
    dominant_house : House

    def get_spouse(self, partner : Person) -> Person:
        return self.partner1 if partner == self.partner2 else self.partner2
    
    
def determine_dominant_house(p1: PersonView, p2: PersonView) -> House | None:
    if p1.is_head and p2.is_head:
        return None  # Two Primarchs marrying? Forbidden politically
    if p1.is_head and not p2.is_head:
        return p1.house
    if p2.is_head and not p1.is_head:
        return p2.house

    if p1.house.is_major_house and not p2.house.is_major_house:
        return p1.house
    if p2.house.is_major_house and not p1.house.is_major_house:
        return p2.house

    if p1.gender == Gender.FEMALE:
        return p2.house
    else:
        return p1.house
    

def find_relationship(deceased: Family, successor: Person) -> str:
    if successor in deceased.children:
        return "daughter" if successor.gender == Gender.FEMALE else "son"

    for child in deceased.children:
        if successor in child.family.children:
            return "grandchild"
        
    if deceased.father and successor.family.father == deceased.father:
        return "sibling"
    if deceased.mother and successor.family.mother == deceased.mother:
        return "sibling"

    if deceased.father:
        for sibling in deceased.siblings():
            if successor in sibling.family.children:
                return "niece" if successor.gender == Gender.FEMALE else "nephew"
    if deceased.mother:
        for sibling in deceased.siblings():
            if successor in sibling.family.children:
                return "niece" if successor.gender == Gender.FEMALE else "nephew"    
    
    deceased_grandparents = set()
    if deceased.father:
        deceased_grandparents.update([deceased.father.family.father, deceased.father.family.mother])
    if deceased.mother:
        deceased_grandparents.update([deceased.mother.family.father, deceased.mother.family.mother])

    successor_grandparents = set()
    if successor.family.father:
        successor_grandparents.update([successor.family.father.family.father, successor.family.father.family.mother])
    if successor.family.mother:
        successor_grandparents.update([successor.family.mother.family.father, successor.family.mother.family.mother])

    if deceased_grandparents.intersection(successor_grandparents):
        return "cousin"

    return "distant relative"