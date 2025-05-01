from __future__ import annotations
import random
import uuid
from renasci.family import Family
from renasci.house import House
from renasci.person import Gender, Life, Person, Sexuality
from renasci.race import Race

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World


def create_person(world : World, race: Race, life: Life, house: House | None = None, first_name: str | None = None, gender: Gender | None = None, is_mainline: bool = False, is_head: bool = False, sexuality: Sexuality | None = None, family : Family | None = None) -> Person:
    gender = gender or random.choice([Gender.MALE, Gender.FEMALE])
    first_name = first_name or race.generate_first_name(gender)
    sexuality = sexuality or Sexuality() #TODO: fly-weight Sexuality.
    family = family or Family()

    return Person(id=str(uuid.uuid4()), world=world, first_name=first_name, gender=gender, house=house, race=race, life=life, sexuality=sexuality, is_mainline=is_mainline, is_head=is_head, family=family)


def create_house(world : World, name : str, start_year : int, founder : Person, is_major_house : bool) -> House:
    house = House(id=str(uuid.uuid4()), world=world, name=name, start_year=start_year, founder=founder, is_major_house=is_major_house)
    founder.house = house
    return house
