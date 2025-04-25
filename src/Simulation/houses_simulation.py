from collections import defaultdict
import random
import uuid
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Union, Literal


random.seed(42)


@dataclass
class Event:
    year: int
    type: Literal["Birth", "Death", "Marriage", "Succession", "Widowed", "Killed"]
    description: str
    payload : Dict[str, Union['Person', 'House']]


# --- RACE PROFILE ---

@dataclass
class RaceProfile:
    name: str
    marriage_age_range: tuple
    lifespan_range: tuple
    childbearing_range: tuple
    birth_rate_modifier : float = 1.0
    namebank: List[str] = field(default_factory=list)
    valid_pairings : List[str] = field(default_factory=list)

    def generate_first_name(self):
        return random.choice(self.namebank)
    
    def death_chance(self, age: int) -> float:
        if age < self.lifespan_range[0]:
            return 0.0
        elif age >= self.lifespan_range[1]:
            return 1.0
        else:
            # Linearly increase from 0 → 1 between min and max
            return (age - self.lifespan_range[0]) / (self.lifespan_range[1] - self.lifespan_range[0])



# --- PERSON ---

@dataclass
class Person:
    id: str
    first_name: str
    gender: str
    house: 'House'
    race: RaceProfile
    birth_year: int
    death_year: Optional[int] = None
    marriage_year: Optional[int] = None
    spouse: Optional['Person'] = None
    sexuality: str = "Heterosexual"
    children: List[str] = field(default_factory=list)
    is_mainline: bool = False
    is_head: bool = False
    is_immortal : bool = False
    father: Optional['Person'] = None
    mother: Optional['Person'] = None
    children: List['Person'] = field(default_factory=list)
    maiden_house: Optional['House'] = None  # for tracking name changes

    @property
    def name(self):
        return f"{self.first_name} {self.house.name}"
    
    @property
    def is_married(self):
        return self.spouse is not None
    
    @property
    def is_alive(self):
        return self.death_year is None
    
    def is_female(self):
        return self.gender == "Female"
    
    def is_heterosexual(self):
        return self.sexuality == "Heterosexual"
    
    def age(self, year :int) -> int:
        return year - self.birth_year

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return str(self)
    
    def __hash__(self):
        return hash(self.id)



@dataclass
class House:
    name: str
    start_year: int
    founder: Person
    major_house: bool = True
    people: Dict[str, Person] = field(default_factory=dict)
    living: List[Person] = field(default_factory=list)

    def __post__init__(self):
        self.add_person(self.founder)

    def add_person(self, person: Person):
        self.people[person.id] = person
        if person.is_alive:
            self.living.append(person)

# --- Event creators ---
def create_birth_event(year: int, child: Person, mother: Person, father: Person) -> Event:
    return Event(
        year=year,
        type="Birth",
        description=f"{child.name} was born to {mother.name} and {father.name}.",
        payload={"mother" : mother, "father" : father, "child" : child}
    )

def create_marriage_event(year: int, p1: Person, p2: Person) -> Event:
    return Event(
        year=year,
        type="Marriage",
        description=f"{p1.name} married {p2.name}.",
        payload={"partner1" : p1, "partner2" : p2}
    )

def create_death_event(year: int, person: Person) -> Event:
    return Event(
        year=year,
        type="Death",
        description=f"{person.name} died.",
        payload={"deceased" : person}
    )

def create_widow_event(year: int, widow: Person, deceased : Person) -> Event:
    return Event(
        year=year,
        type="Widow",
        description=f"{widow.name} was widowed when {deceased.name} died",
        payload={"widow" : widow}
    )

def create_succession_event(year: int, person: Person) -> Event:
    return Event(
        year=year,
        type="Succession",
        description=f"{person.name} became Primarch of House {person.house}.",
        payload={"primarch" : person}
    )
def create_founding_event(year: int, founder: Person) -> Event:
    return Event(
        year=year,
        type="Founding",
        description=f"{founder.name} founded the House {founder.house}.",
        payload={"founder" : founder}
    )

# --- Functional utilities ---

def generate_person(race_profile: RaceProfile, birth_year: int, house: Optional[House] = None, gender: Optional[str] = None, is_mainline: bool = False, is_head: bool = False, sexuality : str = None, first_name : Optional[str] = None, father: Optional[Person] = None, mother: Optional[Person] = None) -> Person:
    gender = gender or random.choice(["Male", "Female"])
    first_name = first_name or race_profile.generate_first_name()
    
    #TODO: Generate sexuality.
    if sexuality is None:
        sexuality = "Heterosexual"
    
    return Person(
        id=str(uuid.uuid4()),
        first_name=first_name,
        gender=gender,
        house=house,
        race=race_profile,
        birth_year=birth_year,
        is_mainline=is_mainline,
        is_head=is_head,
        sexuality=sexuality,
        father=father,
        mother=mother
    )

def found_house(house_name: str, race_profile: RaceProfile, start_year: int, major_house: bool = True, founder : Optional[Person] = None) -> Tuple[Person, House, Event]:
    if founder is None:
        founder = generate_person(race_profile, start_year, is_mainline=True, is_head=True)

    house = House(name=house_name, start_year=start_year, founder=founder, major_house=major_house)
    founder.house = house

    event = create_founding_event(start_year, founder)
    return founder, house, event

def marry(p1: Person, p2: Person, year: int) -> Event:
    p1.marriage_year = year
    p2.marriage_year = year
    p1.spouse = p2
    p2.spouse = p1

    # we do this because we change the names after this point and we want to capture maiden names.
    event = create_marriage_event(year, p1, p2)

    # Rule 1: If one is head of house, the other joins
    if p1.is_head and not p2.is_head:
        p2.maiden_house = p2.house
        p2.house = p1.house
        return event

    if p2.is_head and not p1.is_head:
        p1.maiden_house = p1.house
        p1.house = p2.house
        return event

    # Rule 2: Major > Minor
    if p1.house.major_house and not p2.house.major_house:
        p2.maiden_house = p2.house
        p2.house = p1.house
        return event

    if p2.house.major_house and not p1.house.major_house:
        p1.maiden_house = p1.house
        p1.house = p2.house
        return event

    # Rule 3: Equal standing → female joins male's house
    if p1.gender == "Female":
        p1.maiden_house = p1.house
        p1.house = p2.house
    elif p2.gender == "Female":
        p2.maiden_house = p2.house
        p2.house = p1.house

    return event


def have_child(mother: Person, father: Person, year: int, house : House) -> Tuple[Person, Event]:
    race = mother.race if mother.race == father.race else random.choice([mother.race, father.race])

    child = generate_person(race, year, house=house, father=father, mother=mother, is_mainline=(mother.is_mainline or father.is_mainline))

    mother.children.append(child)
    father.children.append(child)
    house.people[child.id] = child
    house.living.append(child)
    return child, create_birth_event(year, child, mother, father)

def process_death(person: Person, year: int) -> Event:
    person.death_year = year
    if person.id in person.house.living:
        person.house.living.remove(person)
    return create_death_event(year, person)

# --- Utility Function: Get Eligible Singles with Marriage Probability ---
def get_eligible_singles(all_people: Dict[str, Person], year: int) -> List[Person]:
    eligible = []
    for person in all_people.values():
        if person.is_married:
            continue

        age = year - person.birth_year
        # if they're immortal they can ignore the upper bound and remarry after a spouse dies etc. 
        if person.race.marriage_age_range[0] <= age <= person.race.marriage_age_range[1]:
            years_since_eligible = max(0, age - person.race.marriage_age_range[0])
            chance = min(0.10 + 0.05 * years_since_eligible, 0.85)

            if random.random() < chance:
                eligible.append(person)

        # if they're immortal we can have a flat chance. 
        if(age >= person.race.marriage_age_range[0] and person.is_immortal):
            if random.random() < 0.1: #10% chance they decide to get married again.
                eligible.append(person)

    return eligible
# --- Utility Function: Attempt Pairing Eligible Singles into Marriages ---
def attempt_marriages(all_people: Dict[str, Person], year: int) -> List[Event]:
    events : List[Event] = []
    eligible_singles : List[Person] = get_eligible_singles(all_people, year)
    random.shuffle(eligible_singles)
    already_paired = set()

    for person in eligible_singles:
        if person.id in already_paired:
            continue

        potential_partners : List[Person] = []
        for partner in eligible_singles: 
            if partner.id in already_paired:
                continue

            # we can't match with people who are in the same house as us. (yet)
            if person.house == partner.house:
                continue

            # if they're the same gender then to match they need to be gay
            if (person.gender == partner.gender and not(partner.is_heterosexual() or person.is_heterosexual())):
                continue

            # If our partners race isn't in the valid pairings then we can't marry/have children
            if (partner.race.name not in person.race.valid_pairings):
                continue


            potential_partners.append(partner)

        if potential_partners:
            spouse = random.choice(potential_partners)
            event = marry(person, spouse, year)
            events.append(event)

            already_paired.add(person.id)
            already_paired.add(spouse.id)

    return events

# --- Utility Function: Process Deaths ---
def process_deaths(all_people: Dict[str, Person], year: int) -> List[Event]:
    events = []
    for person in all_people.values():
        if not person.is_alive or person.is_immortal:
            continue

        age = person.age(year)
        chance = person.race.death_chance(age)
        if random.random() < chance:
            events.append(process_death(person, year))

    return events

def process_widows(death_events : List[Event], year : int) -> List[Event]:
    events = []
    for death_event in death_events:
        deceased :Person = death_event.payload["deceased"]

        # we could have died in the same year, so only widow people who are alive.
        if not deceased.is_married or deceased.spouse.is_alive:
            continue

        spouse : Person = deceased.spouse
        spouse.spouse = None 
    
        events.append(create_widow_event(year, spouse, deceased))

    return events

# TODO: we'll do this when we have child birthing setup
def process_succession(all_people: Dict[str, Person], year: int) -> List[Event]:
    pass

# --- Utility Function: Process Childbirth ---
def process_childbirths(all_people: Dict[str, Person], year: int) -> List[Event]:
    # find all the married couples. 
    couples : set[tuple[Person, Person]] = set()

    for person in all_people.values():
        if not person.is_alive or not person.is_married or not person.is_heterosexual():
            continue
        couple = tuple(sorted([person, person.spouse], key=lambda e : e.gender)) #if i sort them by gender then mothers will always be first. F > M
        couples.add(couple)
        
    events = []
    for mother, father in couples:
        age = mother.age(year)
        if mother.race.childbearing_range[0] <= age <= mother.race.childbearing_range[1]:
            years_since_eligible = max(0, age - person.race.childbearing_range[0])
            base_chance = min(0.10 + 0.01 * years_since_eligible, 0.25)
            falloff = max(0.01, 0.6 ** (len(mother.children) ** 1.5))
            chance = base_chance * falloff * person.race.birth_rate_modifier

            # print(chance, len(mother.children))

            if random.random() < chance:
                child, event = have_child(mother, father, year, mother.house)
                events.append(event)

                # add the child to the set of people.
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
random.shuffle(base_names)

# Assign lesser houses based on target distribution
race_pool : List[str] = []
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
def simulate_years(start_year: int, end_year: int) -> List[Event]:
    all_people : Dict[str, Person] = {}
    all_houses : Dict[str, House] = {}
    events : List[Event] = []

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

events : List[Event] =  simulate_years(0, 250)
# events.sort(key=lambda e: e.year)
# for event in events:
#     print(f"{event.year} : {event.description}")
 