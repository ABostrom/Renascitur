from __future__ import annotations
import random
from itertools import combinations
from typing import Iterator
from renasci.generators.base import CoreEventGenerator
from renasci.events.person_events import MarriageEvent
from renasci.family import Marriage, determine_dominant_house
from renasci.person import Person
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World



class MarriageGenerator(CoreEventGenerator):
    def generate(self, world: World) -> Iterator[MarriageEvent]:
        eligible_singles = self.get_eligible_singles(world.get_alive_people())
        random.shuffle(eligible_singles)
        already_paired = set()

        for partner, spouse in combinations(eligible_singles, 2):
            if partner in already_paired or spouse in already_paired:
                continue

            if marriage := self.can_marry(partner, spouse, world.current_year):
                yield MarriageEvent.create(world, marriage)
                already_paired.update([partner, spouse])

    def get_eligible_singles(self, all_people: list[Person]) -> list[Person]:
        eligible = []
        for person in all_people:
            if person.is_married:
                continue
            if person.race.marriage_age_range[0] <= person.age <= person.race.marriage_age_range[1]:
                years_since_eligible = max(0, person.age - person.race.marriage_age_range[0])
                chance = min(0.10 + 0.05 * years_since_eligible, 0.85)
                if random.random() < chance:
                    eligible.append(person)
            if person.age >= person.race.marriage_age_range[0] and person.is_immortal:
                if random.random() < 0.1:
                    eligible.append(person)
        return eligible

    def can_marry(self, partner: Person, spouse: Person, year : int) -> Marriage:
        if partner.is_married or spouse.is_married:
            return None
        if determine_dominant_house(partner.to_view(), spouse.to_view()) is None:
            return None
        if not partner.sexuality.is_compatible(partner.gender, spouse.gender):
            return None
        if not partner.race.valid_pairing(spouse.race):
            return None
        
        return Marriage(partner, spouse, year, determine_dominant_house(partner, spouse))