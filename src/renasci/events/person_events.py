from __future__ import annotations
from dataclasses import dataclass
import random

from renasci.events.base import Event
from renasci.events.house_events import HouseChangeEvent
from renasci.family import Family, Marriage, determine_dominant_house, find_relationship

from typing import TYPE_CHECKING

from renasci.person import Life
from renasci.utils.helpers import create_person
if TYPE_CHECKING:
    from renasci.person import Person
    from renasci.house import House
    from renasci.world import World


@dataclass
class DeathEvent(Event):
    deceased : Person

    @classmethod
    def create(cls, world: World, person: Person) -> DeathEvent:
        return cls(
            year=world.current_year,
            type="Death",
            description=f"{person.name} died.",
            world=world,
            deceased=person,
        )

    def apply(self):
        self.deceased.die(self.year)
        self.deceased.house.stats["prestige"] -= 1
        self.world.stats["tension"] += 1
        self.world.stats["prosperity"] -= 1

@dataclass
class SuccessionEvent(Event):
    successor : Person
    deceased : Person

    @classmethod
    def create(cls, world: World, successor: Person, deceased: Person) -> SuccessionEvent:
        relation = find_relationship(deceased.family, successor)
        return cls(
            year=world.current_year,
            type="Succession",
            description=f"Primarch {deceased} is succeeded by their {relation} {successor} as the new Primarch of House {deceased.house}",
            world=world,
            successor=successor,
            deceased=deceased
        )

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
        return SuccessionEvent.create(cause_event.world, successor, deceased) # TODO: not sure on this

    def apply(self):
        self.successor.is_head = True
        self.successor.house.stats["prestige"] += 2
        self.world.stats["tension"] -= 2

        if self.successor.house != self.deceased.house:
            self.world.event_bus.publish(HouseChangeEvent.create(self.world, self.successor, self.deceased.house))

        if self.successor.is_married and self.successor.spouse.house != self.deceased.house:
            self.world.event_bus.publish(HouseChangeEvent.create(self.world, self.successor.spouse, self.deceased.house))

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
    def create(cls, world: World, widow: Person, deceased: Person) -> WidowEvent:
        return cls(
            year=world.current_year,
            type="Widowed",
            description=f"{widow.name} became a widow after {deceased.name}'s death.",
            world=world,
            widow=widow
        )

    @classmethod
    def should_create_from(cls, cause_event: DeathEvent) -> WidowEvent | None:
        if not isinstance(cause_event, DeathEvent):
            return None

        deceased: Person = cause_event.deceased
        if deceased.spouse and deceased.spouse.is_alive:
            return WidowEvent.create(cause_event.world, deceased.spouse, deceased)

        return None

    def apply(self):
        self.widow.marriage = None
        self.widow.stats["loyalty"] -= 10
        self.widow.house.stats["unrest"] += 5


@dataclass
class BirthEvent(Event):
    child : Person 
    mother: Person
    father: Person
    house : House

    @classmethod
    def create(cls, world: World, mother: Person, father: Person, house: House) -> BirthEvent:
        race = mother.race if mother.race == father.race else random.choice([mother.race, father.race])
        child = create_person(
            world=world,
            race=race,
            life=Life(birth_year=world.current_year),
            house=house,
            family=Family(father=father, mother=mother),
            is_mainline=(mother.is_mainline or father.is_mainline)
        )
        return cls(
            year=world.current_year,
            type="Birth",
            description=f"{child.name} was born to {mother.name} and {father.name}.",
            world=world,
            mother=mother,
            father=father,
            child=child,
            house=house,
        )


    def apply(self):
        child = self.child
        self.mother.family.add_child(child)
        self.father.family.add_child(child)
        self.house.add_person(child)
        self.world.add_person(child)
        self.house.stats["prestige"] += 1
        self.world.stats["prosperity"] += 1


@dataclass
class MarriageEvent(Event):
    marriage : Marriage

    @classmethod
    def create(cls, world: World, marriage: Marriage) -> MarriageEvent:
        return cls(
            year=world.current_year,
            type="Marriage",
            description=f"{marriage.partner1} and {marriage.partner2} were married.",
            world=world,
            marriage=marriage
        )

    def apply(self):

        self.marriage.partner1.house.stats["prestige"] += 1
        self.marriage.partner2.house.stats["prestige"] += 1
        self.world.stats["stability"] += 1   

        partner1 = self.marriage.partner1
        partner2 = self.marriage.partner2
        dominant_house = self.marriage.dominant_house

        partner1.marriage = self.marriage
        partner2.marriage = self.marriage

        if partner1.house != dominant_house:
            self.world.event_bus.publish(HouseChangeEvent.create(self.world, partner1, dominant_house))

        if partner2.house != dominant_house:
            self.world.event_bus.publish(HouseChangeEvent.create(self.world, partner2, dominant_house))