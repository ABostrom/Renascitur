# TODO: Refactor these functions to be proper Generator classes.
from __future__ import annotations
from itertools import combinations
import random
from renasci.events.person_events import BirthEvent, DeathEvent, MarriageEvent
from renasci.family import Marriage, determine_dominant_house
from renasci.person import Person
from renasci.world import World


def get_eligible_singles(all_people: list[Person]) -> list[Person]:
    eligible: list[Person] = []
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


# TODO: this could emite a Marriage object
def can_marry(partner : Person, spouse : Person) -> bool:
    # if we can't find a dominant house, then they're not an eligible partner.
    if determine_dominant_house(partner.to_view(), spouse.to_view()) is None:
        return False

    # if we're not sexually compatible we can't marry.
    if not partner.sexuality.is_compatible(partner.gender, spouse.gender):
        return False

    # if we're not a valid pairing
    if not partner.race.valid_pairing(spouse.race):
        return False

    return True

def fertility_chance(age: int, lower: int, upper: int, num_children: int) -> float:
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

    # Ramp up after halfway point
    if progress >= 0.5:
        ramp_multiplier = 1 + (progress - 0.5) * 2
        base_chance *= ramp_multiplier
        base_chance = min(base_chance, 1.0)

    return base_chance

# Generators
def generate_marriages(world : World):
    eligible_singles: list[Person] = get_eligible_singles(world.get_alive_people())
    random.shuffle(eligible_singles)

    already_paired = set()

    for partner, spouse in combinations(eligible_singles, 2):
        if partner in already_paired or spouse in already_paired:
            continue

        if can_marry(partner, spouse):
            world.event_bus.publish(MarriageEvent.create(world, Marriage(partner, spouse, world.current_year, determine_dominant_house(partner, spouse))))
            already_paired.add(partner)
            already_paired.add(spouse)
            

def generate_deaths(world: World):
    for person in world.get_alive_people():
        if person.is_immortal:
            continue

        if random.random() < person.race.death_chance(person.age):
            world.event_bus.publish(DeathEvent.create(world, person))

def generate_births(world : World):
    couples: set[tuple[Person, Person]] = set()

    for person in world.get_alive_people():
        if not person.can_have_children:
            continue

        couple = tuple(sorted([person, person.spouse], key=lambda e: e.gender))
        couples.add(couple)

    for mother, father in couples:
        if random.random() < fertility_chance(mother.age, mother.race.childbearing_range[0], mother.race.childbearing_range[1], len(mother.family.children)):
            world.event_bus.publish(BirthEvent.create(world, mother, father, mother.house))