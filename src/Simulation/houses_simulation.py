from __future__ import annotations

from collections import defaultdict
import random
import uuid
from dataclasses import dataclass, field, replace
from typing import Literal
from itertools import combinations

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
class RaceProfile:
    name: str
    marriage_age_range: tuple[int, int]
    lifespan_range: tuple[int, int]
    childbearing_range: tuple[int, int]
    birth_rate_modifier: float = 1.0
    namebank: list[str] = field(default_factory=list)
    valid_pairings: list[str] = field(default_factory=list)

    def generate_first_name(self) -> str:
        return random.choice(self.namebank)

    def death_chance(self, age: int) -> float:
        if age < self.lifespan_range[0]:
            return 0.0
        elif age >= self.lifespan_range[1]:
            return 1.0
        return (age - self.lifespan_range[0]) / (self.lifespan_range[1] - self.lifespan_range[0])

@dataclass
class Person:
    id: str
    first_name: str
    gender: Literal["Male", "Female"]
    house: House
    race: RaceProfile
    birth_year: int
    death_year: int | None = None
    marriage_year: int | None = None
    spouse: Person | None = None
    sexuality: Literal["Heterosexual"] = "Heterosexual"
    children: list[Person] = field(default_factory=list)
    is_mainline: bool = False
    is_head: bool = False
    is_immortal: bool = False
    father: Person | None = None
    mother: Person | None = None
    maiden_house: House | None = None

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.house.name}"

    @property
    def is_married(self) -> bool:
        return self.spouse is not None

    @property
    def is_alive(self) -> bool:
        return self.death_year is None

    def is_female(self) -> bool:
        return self.gender == "Female"

    def is_heterosexual(self) -> bool:
        return self.sexuality == "Heterosexual"
    
    def is_child_of(self, parent : Person) -> bool:
        return parent in (self.father, self.mother)
    
    def get_living_children(self) -> list[Person]:
        return [child for child in self.children if child.is_alive]

    def age(self, year: int) -> int:
        return year - self.birth_year

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
    living: list[Person] = field(default_factory=list)

    def __post_init__(self):
        self.add_person(self.founder)

    def add_person(self, person: Person):
        self.people[person.id] = person
        if person.is_alive:
            self.living.append(person)

# --- EVENT CREATORS ---
def create_birth_event(year: int, child: Person, mother: Person, father: Person) -> Event:
    return Event(year, "Birth", f"{child.name} was born to {mother.name} and {father.name}.", child.house, {"mother": mother, "father": father, "child": child})

def create_marriage_event(year: int, p1: Person, p2: Person, house: House) -> Event:
    return Event(year, "Marriage", f"{p1.name} married {p2.name}.", house, {"partner1": p1, "partner2": p2})

def create_death_event(year: int, person: Person) -> Event:
    return Event(year, "Death", f"{'Primarch ' if person.is_head else ''}{person.name} died.", person.house, {"deceased": person})

def create_widow_event(year: int, widow: Person, deceased: Person) -> Event:
    return Event(year, "Widowed", f"{widow.name} was widowed when {deceased.name} died", widow.house, {"widow": widow})

def create_succession_event(year: int, person: Person, deceased : Person) -> Event:
    return Event(year, "Succession", f"{person.name} became Primarch of House {person.house.name} succeeding from Primarch {deceased}.", person.house, {"primarch": person})

def create_house_change_event(year: int, person: Person, house : House) -> Event:
    return Event(year, "Succession", f"{person.name} changed allegiance from House {person.house.name} to House {house.name}", person.house, {"house" : house})

def create_founding_event(year: int, founder: Person) -> Event:
    return Event(year, "Founding", f"{founder.name} founded the House {founder.house.name}.", founder.house, {"founder": founder})

def generate_person(race_profile: RaceProfile, birth_year: int, house: House | None = None, gender: str | None = None, is_mainline: bool = False, is_head: bool = False, sexuality: str | None = None, first_name: str | None = None, father: Person | None = None, mother: Person | None = None) -> Person:
    gender = gender or random.choice(["Male", "Female"])
    first_name = first_name or race_profile.generate_first_name()
    sexuality = sexuality or "Heterosexual"
    return Person(str(uuid.uuid4()), first_name, gender, house, race_profile, birth_year, None, None, None, sexuality, [], is_mainline, is_head, False, father, mother)

def found_house(house_name: str, race_profile: RaceProfile, start_year: int, major_house: bool = True, founder: Person | None = None) -> tuple[Person, House, Event]:
    founder = founder or generate_person(race_profile, start_year, is_mainline=True, is_head=True)
    house = House(house_name, start_year, founder, major_house)
    founder.house = house
    return founder, house, create_founding_event(start_year, founder)

def determine_dominant_house(p1: PersonView, p2: PersonView) -> str:
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

    if p1.gender == "Female":
        return p2.house
    else:
        return p1.house


def marry(p1: Person, p2: Person, year: int) -> list[Event]:
    events : list[Event] = []
    p1.marriage_year = year
    p2.marriage_year = year
    p1.spouse = p2
    p2.spouse = p1

    dominant_house = determine_dominant_house(p1.to_view(), p2.to_view())
    events.append(create_marriage_event(year, p1, p2, dominant_house))

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
    child = generate_person(race, year, house=house, father=father, mother=mother, is_mainline=(mother.is_mainline or father.is_mainline))
    mother.children.append(child)
    father.children.append(child)
    house.add_person(child)
    return child, create_birth_event(year, child, mother, father)

def process_death(person: Person, year: int) -> Event:
    person.death_year = year
    if person in person.house.living:
        person.house.living.remove(person)
    return create_death_event(year, person)

def get_eligible_singles(all_people: dict[str, Person], year: int) -> list[Person]:
    eligible: list[Person] = []
    for person in all_people.values():
        if person.is_married:
            continue

        age = year - person.birth_year

        if person.race.marriage_age_range[0] <= age <= person.race.marriage_age_range[1]:
            years_since_eligible = max(0, age - person.race.marriage_age_range[0])
            chance = min(0.10 + 0.05 * years_since_eligible, 0.85)

            if random.random() < chance:
                eligible.append(person)

        if age >= person.race.marriage_age_range[0] and person.is_immortal:
            if random.random() < 0.1:
                eligible.append(person)

    return eligible


def can_marry(partner : Person, spouse : Person) -> bool:
    if determine_dominant_house(partner.to_view(), spouse.to_view()) is None: #if we can't find a dominant house, then they're not an eligible partner.
        return False

    if partner.gender == spouse.gender and not (partner.is_heterosexual() or spouse.is_heterosexual()):
        return False

    if partner.race.name not in spouse.race.valid_pairings:
        return False

    return True


def attempt_marriages(all_people: dict[str, Person], year: int) -> list[Event]:
    events: list[Event] = []

    eligible_singles: list[Person] = get_eligible_singles(all_people, year)
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

def process_deaths(all_people: dict[str, Person], year: int) -> list[Event]:
    events: list[Event] = []
    for person in all_people.values():
        if not person.is_alive or person.is_immortal:
            continue

        age = person.age(year)
        chance = person.race.death_chance(age)
        if random.random() < chance:
            events.append(process_death(person, year))

    return events

def process_widows(death_events: list[Event], year: int) -> list[Event]:
    events: list[Event] = []
    for death_event in death_events:
        deceased: Person = death_event.payload["deceased"]

        if not deceased.is_married or deceased.spouse.is_alive:
            continue

        spouse: Person = deceased.spouse
        spouse.spouse = None

        events.append(create_widow_event(year, spouse, deceased))

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

        if current.father:
            stack.append(current.father)
        if current.mother:
            stack.append(current.mother)

    return ancestors

def is_eligible_successor(successor: Person, deceased : Person) -> bool:
    if not successor.is_alive:
        return False

    if successor.is_head:
        return False

    if successor.is_married:
        spouse = successor.spouse
        if spouse.is_head:
            return False
        
        #Here we use a forward view of IF we changed to this house, and how that would affect the dominant house.
        dominant_house = determine_dominant_house(successor.to_view(overrides={'house':deceased.house, 'is_head':True}), successor.spouse.to_view())
        
        # If successor would not dominate after succession, that's a problem
        if dominant_house != deceased.house:
            return False

    return True


def find_living_descendant(person: Person, deceased : Person) -> Person | None:
    queue = sorted(person.children, key=lambda p: p.birth_year)  # eldest first

    while queue:
        child = queue.pop(0)

        if child.is_alive and is_eligible_successor(child, deceased):
            return child

        queue.extend(sorted(child.children, key=lambda p: p.birth_year))  # expand down

    return None

def find_closest_living_relative(deceased: Person) -> Person | None:
    if candidate := find_living_descendant(deceased, deceased):
        return candidate

    return next((heir for ancestor in collect_ancestors(deceased) if (heir := find_living_descendant(ancestor, deceased))), None)



def process_succession(death_events: list[Event], year: int) -> list[Event]:
    events : list[Event] = []

    for death_event in death_events:
        deceased = death_event.payload["deceased"]
        
        if not deceased.is_head:
            continue  # Only process if the deceased was a Primarch
        
        if successor := find_closest_living_relative(deceased):
            successor.is_head = True

            if successor.house != deceased.house:
                events.append(create_house_change_event(year, successor, deceased.house))

            successor.house = deceased.house

            if successor.is_married:
                if successor.spouse.house != deceased.house:
                    events.append(create_house_change_event(year, successor.spouse, deceased.house))

                successor.spouse.house = deceased.house

            events.append(create_succession_event(year, successor, deceased))
        else:
            #success crisis
            print(f"House Death {deceased.house}")
            pass

    return events


def process_childbirths(all_people: dict[str, Person], year: int) -> list[Event]:
    couples: set[tuple[Person, Person]] = set()

    for person in all_people.values():
        if not person.is_alive or not person.is_married or not person.is_heterosexual():
            continue
        couple = tuple(sorted([person, person.spouse], key=lambda e: e.gender))
        couples.add(couple)

    events: list[Event] = []
    for mother, father in couples:
        age = mother.age(year)
        if mother.race.childbearing_range[0] <= age <= mother.race.childbearing_range[1]:
            years_since_eligible = max(0, age - mother.race.childbearing_range[0])
            base_chance = min(0.10 + 0.01 * years_since_eligible, 0.25)
            falloff = max(0.01, 0.6 ** (len(mother.children) ** 1.5))
            chance = base_chance * falloff * mother.race.birth_rate_modifier

            if random.random() < chance:
                child, event = have_child(mother, father, year, mother.house)
                events.append(event)
                all_people[child.id] = child

    return events

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
race_profiles = {
    "Human": RaceProfile("Human", (20, 35), (75, 90), (20, 45), 1.0, namebanks["Human"], ["Human","Leonin", "Orc"]),
    "Leonin": RaceProfile("Leonin", (20, 35), (85, 100), (20, 45), 1.2, namebanks["Leonin"], ["Human","Leonin", "Orc"]),
    "Orc": RaceProfile("Orc", (18, 30), (65, 80), (18, 40), 1.1, namebanks["Orc"], ["Human","Leonin", "Orc"]),
    "Dwarf": RaceProfile("Dwarf", (50, 100), (300, 500), (50, 200), 0.4, namebanks["Dwarf"], ["Dwarf", "Gnome"]),
    "Gnome": RaceProfile("Gnome", (50, 120), (300, 450), (50, 220), 0.4, namebanks["Gnome"], ["Dwarf", "Gnome"]),
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
print(race_pool)


# create Esravash because she's unique.
Esravash = generate_person(race_profiles["Human"], 0, gender="Female", is_head=True, is_mainline=True, first_name="Esravash")
Esravash.is_immortal = True

founders = defaultdict(lambda: None)
founders["Lyrandar"] = Esravash


# --- Main Simulation Function ---
def simulate_years(start_year: int, end_year: int) -> list[Event]:
    all_people : dict[str, Person] = {}
    all_houses : dict[str, House] = {}
    events : list[Event] = []

    #spawn the major houses
    for house_name, race in house_races.items():
        profile = race_profiles[race]
        person, house, event = found_house(house_name, profile, start_year, True, founders[house_name])
        all_houses[house.name] = house
        all_people[person.id] = person
        events.append(event)

    # spawn the lesser houses.
    for race, house_name in zip(race_pool, base_names):
        profile = race_profiles[race]
        person, house, event = found_house(house_name, profile, start_year, False)
        all_houses[house.name] = house
        all_people[person.id] = person
        events.append(event)


    # need to generate set of random people. 
    # generate 72 more people to help kickstart the civilisation. 
    for race in [*race_pool, *race_pool]:
        filtered_houses = [house for house in all_houses.values() if race in house.founder.race.valid_pairings] #we only want to generate a person in the house that there race valid pair.
        profile = race_profiles[race]
        house : House = random.choice(filtered_houses) # choose a random house from all available.

        # this could make there birth year - but that's fine i think.
        person = generate_person(profile, start_year - random.randrange(0, profile.lifespan_range[0]), house=house)
        all_people[person.id] = person
        all_houses[house.name].add_person(person)

    for year in range(start_year, end_year + 1):
        year_events  = []
        death_events = process_deaths(all_people, year)
        year_events += death_events

        year_events += attempt_marriages(all_people, year)
        year_events += process_childbirths(all_people, year)

        year_events += process_widows(death_events, year)

        year_events += process_succession(death_events, year)

        events += year_events



    # for house in all_houses.values():
    #     amt = sum(
    #         1 for person in house.living
    #         if person.race.name in ["Dwarf", "Gnome"]
    #     )
    #     print(f"{house.name}: {amt} Dwarves/Gnomes")

    # print(len([person for person in all_people.values() if person.is_alive]))

    # for event in events:
    #     print(f"{event.year} : {event.description}")

    return events

events : list[Event] =  simulate_years(0, 100)
events.sort(key=lambda e: e.year)
for event in events:
    #if event.house.name == "Deneith" and event.type in ("Succession", "Death"):
    print(f"{event.year} : {event.description}")
 