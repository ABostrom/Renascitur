import random
import uuid
from renasci.family import Family
from renasci.house import House
from renasci.person import Gender, Life, Person, Sexuality
from renasci.race import Race


def create_person(race: Race, life: Life, house: House | None = None, first_name: str | None = None, gender: Gender | None = None, is_mainline: bool = False, is_head: bool = False, sexuality: Sexuality | None = None, family : Family | None = None) -> Person:
    gender = gender or random.choice([Gender.MALE, Gender.FEMALE])
    first_name = first_name or race.generate_first_name()
    sexuality = sexuality or Sexuality() #TODO: fly-weight Sexuality.
    family = family or Family()

    return Person(id=str(uuid.uuid4()), first_name=first_name, gender=gender, house=house, race=race, life=life, sexuality=sexuality, is_mainline=is_mainline, is_head=is_head, family=family)
