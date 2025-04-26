from __future__ import annotations

from collections import defaultdict
import random
import uuid
from dataclasses import dataclass, field, replace
from typing import Literal, Callable
from itertools import combinations
from enum import Enum


class EventBus:
    def __init__(self):
        self.subscribers: dict[str, list[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)

    def publish(self, event: Event):
        handlers = self.subscribers.get(event.type, [])
        for handler in handlers:
            handler(event)


@dataclass
class Event:
    year: int
    type: Literal["Birth", "Death", "Marriage", "Succession", "Widowed", "Killed", "Founding"]
    description: str
    house : House
    payload: dict[str, Person]


@dataclass
class PersonView:
    is_head : bool
    gender : str
    house : House

@dataclass
class Race:
    name: Literal["Human", "Leonin", "Orc", "Dwarf", "Gnome"]
    marriage_age_range: tuple[int, int]
    lifespan_range: tuple[int, int]
    childbearing_range: tuple[int, int]
    namebank: list[str] = field(default_factory=list)
    valid_pairings: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return self.name
    
    def generate_first_name(self) -> str:
        return random.choice(self.namebank)
    
    def valid_pairing(self, race : Race) -> bool:
        return race.name in self.valid_pairings

    def death_chance(self, age: int) -> float:
        if age < self.lifespan_range[0]:
            return 0.0
        elif age >= self.lifespan_range[1]:
            return 1.0
        return (age - self.lifespan_range[0]) / (self.lifespan_range[1] - self.lifespan_range[0])


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
    value: Literal["Heterosexual", "Homosexual", "Bisexual", "Asexual"] = "Heterosexual"

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

@dataclass
class Life:
    birth_year: int | None = None
    age : int = 0
    is_alive : bool = True
    death_year: int | None = None

    def __str__(self) -> str:
        return str(self.age)

    def __repr__(self) -> str:
        return str(self.age)

    def die(self, year: int):
        self.death_year = year
        self.is_alive = False


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

    def get_spouse(self, partner : Person) -> Person:
        return self.partner1 if partner == self.partner2 else self.partner2


@dataclass
class Person:
    id: str
    first_name: str
    gender: Gender
    house: House
    race: Race
    life: Life
    sexuality: Sexuality = field(default_factory=lambda: Sexuality("Heterosexual"))
    family: Family = field(default_factory=Family)
    marriage: Marriage | None = None
    is_mainline: bool = False
    is_head: bool = False
    is_immortal: bool = False
    maiden_house: House | None = None  # for marriage name changes

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.house.name}"

    @property
    def is_married(self) -> bool:
        return self.marriage is not None

    @property
    def is_alive(self) -> bool:
        return self.life.is_alive 
            
    @property
    def age(self) -> int:
        return self.life.age
    
    @property
    def spouse(self) -> Person | None:
        return self.marriage.get_spouse(self) if self.is_married else None
    
    @property
    def can_have_children(self) -> bool:
        return self.is_married and self.gender == Gender.FEMALE and self.marriage.get_spouse(self).gender == self.gender.get_opposite()
    
    def die(self, year: int):
        self.life.die(year)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)

    def __hash__(self) -> int:
        return hash(self.id)
    
    def to_view(self, overrides: dict = None) -> PersonView:
        overrides = overrides or {}

        return PersonView(
            house=overrides.get('house', self.house),
            is_head=overrides.get('is_head', self.is_head),
            gender=overrides.get('gender', self.gender),
        )


@dataclass
class House:
    name: str
    start_year: int
    founder: Person
    major_house: bool = True
    people: dict[str, Person] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return str(self)
    
    def __post_init__(self):
        self.add_person(self.founder)

    def add_person(self, person: Person):
        self.people[person.id] = person

@dataclass
class World:
    current_year: int
    people: dict[str, Person] = field(default_factory=dict)
    houses: dict[str, House] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)

    def advance_year(self):
        self.current_year += 1
        for person in self.get_alive_people():
            person.life.age += 1

    def add_people(self, people : list[Person]):
        for person in people : self.add_person(person)

    def add_person(self, person: Person):
        self.people[person.id] = person

    def add_house(self, house: House):
        self.houses[house.name] = house

    def add_event(self, event: Event):
        self.events.append(event)

    def get_alive_people(self) -> list[Person]:
        return [p for p in self.people.values() if p.is_alive]


# --- EVENT CREATORS ---
def create_birth_event(year: int, child: Person, mother: Person, father: Person) -> Event:
    return Event(year, "Birth", f"{child.name} was born to {mother.name} and {father.name}.", child.house, {"mother": mother, "father": father, "child": child})

def create_marriage_event(year: int, marriage : Marriage, house: House) -> Event:
    return Event(year, "Marriage", f"{marriage.partner1} married {marriage.partner2}.", house, {"marriage": marriage})

def create_death_event(year: int, person: Person) -> Event:
    return Event(year, "Death", f"{'Primarch ' if person.is_head else ''}{person.name} died.", person.house, {"deceased": person})

def create_widow_event(year: int, widow: Person, deceased: Person) -> Event:
    return Event(year, "Widowed", f"{widow.name} was widowed when {deceased.name} died", widow.house, {"widow": widow})

def create_succession_event(year: int, person: Person, deceased : Person) -> Event:
    return Event(year, "Succession", f"Primarch {deceased} is succeeded by their {find_relationship(deceased.family, person)} {person.name} as the new Primarch of House {person.house.name}", person.house, {"primarch": person})

def create_house_change_event(year: int, person: Person, house : House) -> Event:
    return Event(year, "Succession", f"{person.name} changed allegiance from House {person.house.name} to House {house.name}", person.house, {"house" : house})

def create_founding_event(year: int, founder: Person) -> Event:
    return Event(year, "Founding", f"{founder.name} founded the House {founder.house.name}.", founder.house, {"founder": founder})


def handle_birth(event: Event):
    pass

def handle_death(event: Event):
    pass

def handle_marriage(event: Event):
    pass

def handle_succession(event: Event):
    pass

def handle_widowed(event: Event):
    pass



def generate_person(race: Race, life: Life, house: House | None = None, first_name: str | None = None, gender: Gender | None = None, is_mainline: bool = False, is_head: bool = False, sexuality: Sexuality | None = None, family : Family | None = None) -> Person:
    gender = gender or random.choice([Gender.MALE, Gender.FEMALE])
    first_name = first_name or race.generate_first_name()
    sexuality = sexuality or Sexuality() #TODO: fly-weight Sexuality.
    family = family or Family()

    return Person(id=str(uuid.uuid4()), first_name=first_name, gender=gender, house=house, race=race, life=life, sexuality=sexuality, is_mainline=is_mainline, is_head=is_head, family=family)

def found_house(house_name: str, race: Race, start_year: int, major_house: bool = True, founder: Person | None = None) -> tuple[list[Person], House, Event]:
    # If a founder is pre-provided, use it
    # for founders and foudners spouse we don't give them a birth year just an age.
    founder = founder or generate_person(race=race, life=Life(age=random.randint(*race.marriage_age_range)), is_mainline=True, is_head=True)

    house = House(house_name, start_year, founder, major_house)
    founder.house = house

    spouse_gender = founder.gender.get_opposite()
    spouse = generate_person(race=race, life=Life(age=random.randint(*race.marriage_age_range)), house=house, gender=spouse_gender)

    marry(founder, spouse, start_year) # choosing not to record the marriage events, because this is just when history began.
    event = create_founding_event(start_year, founder)
    return [founder, spouse], house, event

def determine_dominant_house(p1: PersonView, p2: PersonView) -> House | None:
    if p1.is_head and p2.is_head:
        return None  # Two Primarchs marrying? Forbidden politically
    if p1.is_head and not p2.is_head:
        return p1.house
    if p2.is_head and not p1.is_head:
        return p2.house

    if p1.house.major_house and not p2.house.major_house:
        return p1.house
    if p2.house.major_house and not p1.house.major_house:
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

def marry(p1: Person, p2: Person, year: int) -> list[Event]:
    events : list[Event] = []

    marriage = Marriage(p1, p2, year)
    p1.marriage = marriage
    p2.marriage = marriage

    dominant_house = determine_dominant_house(p1.to_view(), p2.to_view())
    events.append(create_marriage_event(year, marriage, dominant_house))

    if p1.house != dominant_house:
        events.append(create_house_change_event(year, p1, dominant_house))
        p1.maiden_house = p1.house
        p1.house = dominant_house
        
    if p2.house != dominant_house:
        events.append(create_house_change_event(year, p2, dominant_house))
        p2.maiden_house = p2.house
        p2.house = dominant_house
        
    return events

def have_child(mother: Person, father: Person, year: int, house: House) -> tuple[Person, Event]:
    race = mother.race if mother.race == father.race else random.choice([mother.race, father.race])
    child = generate_person(race, Life(birth_year=year), house=house, family=Family(father=father, mother=mother), is_mainline=(mother.is_mainline or father.is_mainline))

    # TODO: think we can make this better.
    mother.family.add_child(child)
    father.family.add_child(child)
    house.add_person(child)

    return child, create_birth_event(year, child, mother, father)

def process_death(person: Person, year: int) -> Event:
    person.die(year)
    return create_death_event(year, person)

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

def generate_marriages(people: list[Person], year: int) -> list[Event]:
    events: list[Event] = []

    eligible_singles: list[Person] = get_eligible_singles(people)
    random.shuffle(eligible_singles)

    already_paired = set()

    for partner, spouse in combinations(eligible_singles, 2):
        if partner in already_paired or spouse in already_paired:
            continue

        if can_marry(partner, spouse):
            events += marry(partner, spouse, year)
            already_paired.add(partner)
            already_paired.add(spouse)

    return events

def process_deaths(people: list[Person], year: int) -> list[Event]:
    events: list[Event] = []
    for person in people:
        if person.is_immortal:
            continue

        chance = person.race.death_chance(person.age)
        if random.random() < chance:
            events.append(process_death(person, year))

    return events

def process_widows(death_events: list[Event]) -> list[Event]:
    events: list[Event] = []
    for death_event in death_events:
        deceased: Person = death_event.payload["deceased"]

        if not deceased.is_married or deceased.spouse.is_alive:
            continue

        spouse: Person = deceased.spouse
        spouse.marriage = None # end the marriage.
        events.append(create_widow_event(deceased.life.death_year, spouse, deceased))

    return events

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

def find_living_descendant(family: Family, deceased : Person) -> Person | None:
    queue = family.get_children_age_sorted()  # eldest first

    while queue:
        child = queue.pop(0)

        if child.is_alive and is_eligible_successor(child, deceased):
            return child

        queue += child.family.get_children_age_sorted()  # expand down

    return None

def find_closest_living_relative(deceased: Person) -> Person | None:
    if candidate := find_living_descendant(deceased.family, deceased):
        return candidate

    return next((heir for ancestor in collect_ancestors(deceased) if (heir := find_living_descendant(ancestor.family, deceased))), None)

def process_succession(death_events: list[Event]) -> list[Event]:
    events : list[Event] = []

    for death_event in death_events:
        deceased = death_event.payload["deceased"]
        
        if not deceased.is_head:
            continue  # Only process if the deceased was a Primarch
        
        if successor := find_closest_living_relative(deceased):
            successor.is_head = True

            if successor.house != deceased.house:
                events.append(create_house_change_event(deceased.life.death_year, successor, deceased.house))

            successor.house = deceased.house

            if successor.is_married:
                if successor.spouse.house != deceased.house:
                    events.append(create_house_change_event(deceased.life.death_year, successor.spouse, deceased.house))

                successor.spouse.house = deceased.house

            events.append(create_succession_event(deceased.life.death_year, successor, deceased))
        else:
            # Could pick the oldest in the house - might not be related to the head.
            #success crisis
            # need to refactor the checks above in case the person we choose is somehow wrong.
            print(f"House Death {deceased.house} {deceased.race}")

    return events

def fertility_chance(age: int, lower: int, upper: int, num_children: int) -> float:
    if age < lower or age > upper:
        return 0.0

    total_years = upper - lower
    progress = (age - lower) / total_years
    base_chance = 3 / total_years  # targeting 3 children per woman

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

def process_childbirths(people: list[Person], year: int) -> tuple[list[Person], list[Event]]:
    couples: set[tuple[Person, Person]] = set()

    for person in people:
        if not person.can_have_children:
            continue

        couple = tuple(sorted([person, person.spouse], key=lambda e: e.gender))
        couples.add(couple)

    events: list[Event] = []
    children : list[Person] = []
    for mother, father in couples:
        if random.random() < fertility_chance(mother.age, mother.race.childbearing_range[0], mother.race.childbearing_range[1], len(mother.family.children)):
            child, event = have_child(mother, father, year, mother.house)
            events.append(event)
            children.append(child)

    return children, events


def make_world(start_year : int) -> World:
    # Expanded namebanks for full-scale simulation
    namebanks = {
        "Human": [
            "Aerin", "Kaelen", "Mira", "Tavian", "Lira", "Galen", "Soren", "Vasha", "Dalia", "Ren",
            "Lucan", "Selene", "Marcus", "Elandra", "Julen", "Anika", "Corwin", "Isolde", "Valen", "Neris",
            "Darien", "Thalia", "Seren", "Cassian", "Lyra", "Elias", "Virel", "Arden", "Talwin", "Orlan",
            "Jorah", "Nyra", "Caius", "Ilyana", "Quint", "Arista", "Delan", "Soraya", "Theron", "Mariel",
            "Riven", "Erella", "Faelan", "Brynn", "Caelan", "Lucina", "Maelis", "Torren", "Alaric", "Vestra",
            "Jasmin", "Dorian", "Kira", "Laziel", "Selar", "Viren", "Nalia", "Oryn", "Cerys", "Thalen"
        ],
        "Leonin": [
            "Tharek", "Khera", "Roan", "Zarek", "Sahria", "Korren", "Nahlia", "Dravon", "Shael", "Varn",
            "Jakar", "Marha", "Zareen", "Raskan", "Lareth", "Savra", "Harkan", "Yalira", "Braxis", "Noma",
            "Karn", "Feris", "Rasha", "Dornak", "Varra", "Torken", "Sharai", "Lazhar", "Tharn", "Mirath",
            "Torak", "Zemra", "Kassan", "Varek", "Rhakar", "Malra", "Dakar", "Narish", "Kovra", "Silrek",
            "Yaren", "Tholkar", "Zharan", "Jurek", "Nashara", "Volrik", "Kavren", "Draska", "Orrek", "Zhara"
        ],
        "Orc": [
            "Brakka", "Thok", "Urgra", "Zarn", "Mokha", "Draven", "Gorza", "Rok", "Drezza", "Volg",
            "Karnok", "Sharga", "Thurz", "Grasha", "Borzak", "Murka", "Dorgul", "Varka", "Thrask", "Urna",
            "Krog", "Zurka", "Blazra", "Togga", "Gorran", "Rugha", "Zugrak", "Brahz", "Thoga", "Kral",
            "Murz", "Vashka", "Skarn", "Krutha", "Barzug", "Grotha", "Yargul", "Zarna", "Rugok", "Darza",
            "Kurg", "Zharok", "Kazzak", "Drogna", "Sharn", "Grukk", "Bragha", "Thurg", "Rakha", "Zolrak"
        ],
        "Dwarf": [
            "Thrain", "Gilda", "Korin", "Durra", "Brokk", "Marnin", "Thorek", "Helga", "Brand", "Orla",
            "Harrek", "Brunna", "Dorgar", "Frida", "Grundin", "Sigrid", "Barik", "Elka", "Torgrim", "Inga",
            "Kelda", "Hroth", "Mavrik", "Vala", "Balin", "Svala", "Drakka", "Eirik", "Ylva", "Drogan",
            "Thrainor", "Falka", "Grunna", "Ralgar", "Tharnor", "Astrid", "Grom", "Gudrun", "Dagna", "Halrik",
            "Orm", "Vigdis", "Kelgar", "Sigga", "Norrik", "Elda", "Thorig", "Ragnor", "Ketta", "Skarn"
        ],
        "Gnome": [
            "Zimble", "Brassel", "Feigen", "Tinkel", "Fizzwick", "Wizzle", "Glim", "Rizzy", "Nim", "Bramble",
            "Pindle", "Yoffa", "Snorri", "Miska", "Grindle", "Flora", "Voddle", "Nana", "Fibble", "Klem",
            "Gilda", "Doffa", "Jorra", "Nackle", "Tilly", "Pizzen", "Lemmi", "Zurra", "Moppy", "Zevan",
            "Wobble", "Gressel", "Jaxit", "Trilla", "Yana", "Bimble", "Tibbin", "Narla", "Quix", "Nixie",
            "Zibble", "Yettel", "Krissa", "Dakka", "Loof", "Ravva", "Winni", "Fessel", "Droppi", "Zekka"
        ]
    }

    # Create race profile objects
    races = {
        "Human":    Race("Human",   (20, 35),   (75, 90),   (20, 45),   namebanks["Human"],     ["Human","Leonin", "Orc"]),
        "Leonin":   Race("Leonin",  (20, 35),   (85, 100),  (20, 45),   namebanks["Leonin"],    ["Human","Leonin", "Orc"]),
        "Orc":      Race("Orc",     (18, 30),   (65, 80),   (18, 40),   namebanks["Orc"],       ["Human","Leonin", "Orc"]),
        "Dwarf":    Race("Dwarf",   (50, 100),  (300, 500), (50, 200),  namebanks["Dwarf"],     ["Dwarf", "Gnome"]),
        "Gnome":    Race("Gnome",   (50, 120),  (300, 450), (50, 220),  namebanks["Gnome"],     ["Dwarf", "Gnome"]),
    }

    # House -> race mapping
    house_races = {
        "Medani": "Leonin",
        "Tharashk": "Leonin",
        "Vadalis": "Human",
        "Jorasco": "Human",
        "Silverhand": "Gnome",
        "Cannith": "Human",
        "Orien": "Orc",
        "Sivis": "Human",
        "Deneith": "Leonin",
        "Phiarlan": "Leonin",
        "Lyrandar": "Human",
        "Kundarak": "Dwarf"
    }

    # Distribution
    lesser_distribution = {
        "Leonin": 10,
        "Orc": 10,
        "Human": 10,
        "Gnome": 3,
        "Dwarf": 3
    }

    # Generate 36 unique lesser house names (pseudo-Latin style, can be enhanced)
    base_names = [
        "Valcoris", "Tarneth", "Branovar", "Solvannis", "Drakhal", "Marnax", "Velthuron", "Thiravin",
        "Elgaris", "Korveth", "Mirellan", "Dornak", "Theskar", "Jendral", "Kareth", "Ulmarin",
        "Vorannis", "Zorath", "Mirethorn", "Beldannis", "Grellan", "Skarneth", "Orravan", "Telmuris",
        "Varnak", "Quenlor", "Harthan", "Zeruvan", "Kolmir", "Grendhal", "Ravikar", "Vondrell", 
        "Thessan", "Drelgar", "Nemorin", "Caraveth"
    ]

    random.seed(42)
    random.shuffle(base_names)

    # Assign lesser houses based on target distribution
    race_pool : list[str] = []
    for race, count in lesser_distribution.items():
        race_pool.extend([race] * count)

    random.shuffle(race_pool)

    # create Esravash because she's unique.
    Esravash = generate_person(race=races["Human"], life=Life(0, 30), gender=Gender.FEMALE, is_head=True, is_mainline=True, first_name="Esravash")
    Esravash.is_immortal = True

    founders = defaultdict(lambda: None)
    founders["Lyrandar"] = Esravash

    all_people : dict[str, Person] = {}
    all_houses : dict[str, House] = {}
    events : list[Event] = []

    #spawn the major houses
    for house_name, race_name in house_races.items():
        (founder, spouse), house, event = found_house(house_name, races[race_name], start_year, True, founders[house_name])
        all_houses[house.name] = house
        all_people[founder.id] = founder
        all_people[spouse.id] = spouse
        events.append(event)

    # spawn the lesser houses.
    for race_name, house_name in zip(race_pool, base_names):
        (founder, spouse), house, event = found_house(house_name, races[race_name], start_year, False)
        all_houses[house.name] = house
        all_people[founder.id] = founder
        all_people[spouse.id] = spouse
        events.append(event)


    return World(start_year, all_people, all_houses, events)

# --- Main Simulation Function ---
def simulate_years(world : World, end_year: int):
    for year in range(world.current_year, end_year + 1):
        # make everyone one year older as the year is over
        world.advance_year()
        living_people : list[Person] = world.get_alive_people()

        year_events  = []
        death_events = process_deaths(living_people, year)
        year_events += death_events

        year_events += generate_marriages(living_people, year)

        children, birth_events = process_childbirths(living_people, year)
        world.add_people(children)
        year_events += birth_events

        year_events += process_widows(death_events)

        year_events += process_succession(death_events)

        world.events += year_events

world = make_world(0)
simulate_years(world, 250)
world.events.sort(key=lambda e: e.year)
for event in world.events:
    print(f"{event.year} : {event.description}")


# for person in world.people.values():
#     if person.gender == Gender.FEMALE and person.is_married:
#         print(person, person.age, len(person.family.children))
# print(len(world.get_alive_people()))
 