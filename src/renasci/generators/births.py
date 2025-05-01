from __future__ import annotations
import random
from typing import Iterator
from renasci.generators.base import EventGenerator
from renasci.events.person_events import BirthEvent
from typing import TYPE_CHECKING

from renasci.person import Person
if TYPE_CHECKING:
    from renasci.world import World

class BirthGenerator(EventGenerator):
    def generate(self, world: World) -> Iterator[BirthEvent]:
        couples : set[tuple[Person, Person]] = set()
        for person in world.get_alive_people():
            if not person.can_have_children:
                continue
            couple = tuple(sorted([person, person.spouse], key=lambda e: e.gender))
            couples.add(couple)

        for mother, father in couples:
            chance = self.fertility_chance(mother.age, mother.race.childbearing_range[0],
                                      mother.race.childbearing_range[1], len(mother.family.children))
            if random.random() < chance:
                yield BirthEvent.create(world, mother, father, mother.house)

    def fertility_chance(self, age: int, lower: int, upper: int, num_children: int) -> float:
        if age < lower or age > upper:
            return 0.0

        total_years = upper - lower
        progress = (age - lower) / total_years
        base_chance = 4 / total_years  # targeting 4 children per woman

        if num_children == 1:
            base_chance *= 0.8
        elif num_children == 2:
            base_chance *= 0.5
        elif num_children >= 3:
            base_chance *= 0.1

        if progress >= 0.5:
            ramp_multiplier = 1 + (progress - 0.5) * 2
            base_chance *= ramp_multiplier
            base_chance = min(base_chance, 1.0)

        return base_chance
