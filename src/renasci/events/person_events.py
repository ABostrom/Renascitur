from __future__ import annotations
from dataclasses import dataclass

from renasci.events.base import Event
from renasci.family import Family, Marriage, determine_dominant_house

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.person import Person
    from renasci.house import House


@dataclass
class DeathEvent(Event):
    deceased : Person

    def apply(self):
        self.deceased.die(self.year)

@dataclass
class SuccessionEvent(Event):
    successor : Person
    deceased : Person

    @classmethod
    def should_create_from(cls, cause_event: DeathEvent) -> SuccessionEvent | None:
        if not isinstance(cause_event, DeathEvent):
            return None
        
        deceased = cause_event.deceased
        if not deceased.is_head:
            return None

        successor = SuccessionEvent.find_closest_living_relative(deceased)
        if not successor:
            return None
        from renasci.events.helpers import  create_succession_event
        return create_succession_event(cause_event.world, successor, deceased) # TODO: not sure on this

    def apply(self):
        self.successor.is_head = True


        from renasci.events.helpers import  create_house_change_event
        if self.successor.house != self.deceased.house:
            self.world.event_bus.publish(create_house_change_event(self.world, self.successor, self.deceased.house))

        if self.successor.is_married and self.successor.spouse.house != self.deceased.house:
            self.world.event_bus.publish(create_house_change_event(self.world, self.successor.spouse, self.deceased.house))

    @staticmethod
    def collect_ancestors(person: Person) -> list[Person]:
        ancestors = []
        stack = [person]

        visited :set[Person] = set()
        while stack:
            current :Person = stack.pop()
            if current in visited:
                continue

            visited.add(current)
            ancestors.append(current)

            if current.family.father:
                stack.append(current.family.father)
            if current.family.mother:
                stack.append(current.family.mother)

        return ancestors

    @staticmethod
    def is_eligible_successor(successor: Person, deceased : Person) -> bool:
        if not successor.is_alive:
            return False

        if successor.is_head:
            return False

        if spouse := successor.spouse:
            if spouse.is_head:
                return False
            
            #Here we use a forward view of IF we changed to this house, and how that would affect the dominant house.
            dominant_house = determine_dominant_house(successor.to_view(overrides={'house':deceased.house, 'is_head':True}), successor.spouse.to_view())
            
            # If successor would not dominate after succession, that's a problem
            if dominant_house != deceased.house:
                return False

        return True

    @staticmethod
    def find_living_descendant(family: Family, deceased : Person) -> Person | None:
        queue : list[Person] = family.get_children_age_sorted()  # eldest first

        while queue:
            child = queue.pop(0)

            if child.is_alive and SuccessionEvent.is_eligible_successor(child, deceased):
                return child

            queue += child.family.get_children_age_sorted()  # expand down

        return None

    @staticmethod
    def find_closest_living_relative(deceased : Person) -> Person | None:
        if candidate := SuccessionEvent.find_living_descendant(deceased.family, deceased):
            return candidate

        return next((heir for ancestor in SuccessionEvent.collect_ancestors(deceased) if (heir := SuccessionEvent.find_living_descendant(ancestor.family, deceased))), None)

@dataclass
class WidowEvent(Event):
    widow : Person

    @classmethod
    def should_create_from(cls, cause_event: DeathEvent) -> WidowEvent | None:
        if not isinstance(cause_event, DeathEvent):
            return None

        deceased: Person = cause_event.deceased
        if deceased.spouse and deceased.spouse.is_alive:
            from renasci.events.helpers import create_widowed_event
            return create_widowed_event(cause_event.world, deceased.spouse, deceased)

        return None

    def apply(self):
        self.widow.marriage = None


@dataclass
class BirthEvent(Event):
    child : Person 
    mother: Person
    father: Person
    house : House

    def apply(self):
        child = self.child
        self.mother.family.add_child(child)
        self.father.family.add_child(child)
        self.house.add_person(child)
        self.world.add_person(child)



@dataclass
class MarriageEvent(Event):
    marriage : Marriage

    def apply(self):       
        partner1 = self.marriage.partner1
        partner2 = self.marriage.partner2
        dominant_house = self.marriage.dominant_house

        partner1.marriage = self.marriage
        partner2.marriage = self.marriage

        from renasci.events.helpers import  create_house_change_event
        if partner1.house != dominant_house:
            self.world.event_bus.publish(create_house_change_event(self.world, partner1, dominant_house))

        if partner2.house != dominant_house:
            self.world.event_bus.publish(create_house_change_event(self.world, partner2, dominant_house))