from collections import defaultdict
import random
from renasci.events.generators import generate_births, generate_deaths, generate_marriages
from renasci.events.house_events import FoundingEvent
from renasci.person import Gender, Life
from renasci.utils.helpers import create_person
from renasci.world import World
from renasci.race import Race

def generate_world(start_year : int) -> World:
    # Expanded namebanks for full-scale simulation
    namebanks = {
        "Human": {
            Gender.MALE: [
                "Aerin", "Kaelen", "Tavian", "Galen", "Soren", "Ren", "Lucan", "Marcus", "Julen", "Corwin",
                "Valen", "Darien", "Cassian", "Elias", "Virel", "Arden", "Talwin", "Orlan", "Jorah", "Caius",
                "Quint", "Delan", "Theron", "Riven", "Faelan", "Caelan", "Torren", "Alaric", "Dorian", "Selar",
                "Viren", "Oryn", "Thalen"
            ],
            Gender.FEMALE: [
                "Mira", "Lira", "Vasha", "Dalia", "Selene", "Elandra", "Anika", "Isolde", "Neris", "Thalia",
                "Seren", "Lyra", "Nyra", "Ilyana", "Arista", "Soraya", "Mariel", "Erella", "Brynn", "Lucina",
                "Maelis", "Vestra", "Jasmin", "Kira", "Laziel", "Nalia", "Cerys"
            ]
        },
        "Leonin": {
            Gender.MALE: [
                "Tharek", "Roan", "Zarek", "Korren", "Dravon", "Varn", "Jakar", "Raskan", "Harkan", "Braxis",
                "Karn", "Feris", "Dornak", "Torken", "Lazhar", "Tharn", "Torak", "Kassan", "Rhakar", "Dakar",
                "Kovra", "Silrek", "Tholkar", "Zharan", "Jurek", "Volrik", "Kavren", "Orrek"
            ],
            Gender.FEMALE: [
                "Khera", "Sahria", "Nahlia", "Shael", "Marha", "Zareen", "Lareth", "Savra", "Yalira", "Noma",
                "Rasha", "Varra", "Sharai", "Mirath", "Zemra", "Malra", "Narish", "Yaren", "Nashara", "Draska", "Zhara"
            ]
        },
        "Orc": {
            Gender.MALE: [
                "Brakka", "Thok", "Zarn", "Draven", "Rok", "Volg", "Karnok", "Thurz", "Borzak", "Dorgul",
                "Varka", "Thrask", "Krog", "Togga", "Gorran", "Zugrak", "Brahz", "Thoga", "Kral", "Murz",
                "Skarn", "Barzug", "Yargul", "Rugok", "Kurg", "Zharok", "Kazzak", "Drogna", "Grukk", "Thurg", "Rakha", "Zolrak"
            ],
            Gender.FEMALE: [
                "Urgra", "Mokha", "Gorza", "Drezza", "Grasha", "Murka", "Urna", "Zurka", "Blazra", "Rugha",
                "Vashka", "Krutha", "Grotha", "Zarna", "Darza", "Sharga", "Sharn", "Bragha"
            ]
        },
        "Dwarf": {
            Gender.MALE: [
                "Thrain", "Korin", "Brokk", "Marnin", "Thorek", "Brand", "Harrek", "Dorgar", "Grundin", "Barik",
                "Torgrim", "Balin", "Eirik", "Drogan", "Thrainor", "Ralgar", "Tharnor", "Grom", "Halrik", "Orm",
                "Kelgar", "Norrik", "Thorig", "Ragnor", "Skarn"
            ],
            Gender.FEMALE: [
                "Gilda", "Durra", "Helga", "Orla", "Brunna", "Frida", "Sigrid", "Elka", "Inga", "Kelda",
                "Vala", "Svala", "Drakka", "Ylva", "Falka", "Grunna", "Astrid", "Gudrun", "Dagna", "Vigdis",
                "Sigga", "Elda", "Ketta"
            ]
        },
        "Gnome": {
            Gender.MALE: [
                "Zimble", "Brassel", "Feigen", "Tinkel", "Fizzwick", "Wizzle", "Glim", "Bramble", "Pindle", "Snorri",
                "Grindle", "Voddle", "Fibble", "Klem", "Doffa", "Nackle", "Pizzen", "Lemmi", "Zurra", "Zevan",
                "Wobble", "Gressel", "Jaxit", "Tibbin", "Quix", "Zibble", "Loof", "Fessel"
            ],
            Gender.FEMALE: [
                "Rizzy", "Nim", "Yoffa", "Miska", "Flora", "Nana", "Gilda", "Jorra", "Tilly", "Moppy",
                "Trilla", "Yana", "Bimble", "Narla", "Nixie", "Yettel", "Krissa", "Dakka", "Ravva", "Winni",
                "Droppi", "Zekka"
            ]
        }
    }

    # Create race profile objects
    races = {
        "Human":    Race("Human",   (20, 35),   (75, 90),   (20, 45),   namebanks["Human"],     ["Human","Leonin", "Orc"]),
        "Leonin":   Race("Leonin",  (20, 35),   (85, 100),  (20, 45),   namebanks["Leonin"],    ["Human","Leonin", "Orc"]),
        "Orc":      Race("Orc",     (18, 30),   (65, 80),   (18, 40),   namebanks["Orc"],       ["Human","Leonin", "Orc"]),
        "Dwarf":    Race("Dwarf",   (50, 100),  (300, 500), (50, 200),  namebanks["Dwarf"],     ["Dwarf", "Gnome"]),
        "Gnome":    Race("Gnome",   (50, 120),  (300, 450), (50, 220),  namebanks["Gnome"],     ["Dwarf", "Gnome"]),
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
    Esravash = create_person(race=races["Human"], life=Life(0, 30), gender=Gender.FEMALE, is_head=True, is_mainline=True, first_name="Esravash")
    Esravash.is_immortal = True

    founders = defaultdict(lambda: None)
    founders["Lyrandar"] = Esravash
    
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


    world = World(start_year)

    #spawn the major houses
    for house_name, race_name in house_races.items():
        world.event_bus.publish(FoundingEvent.create(world, house_name, races[race_name], start_year, True, founders[house_name]))

    # spawn the lesser houses.
    for race_name, house_name in zip(race_pool, base_names):
        world.event_bus.publish(FoundingEvent.create(world, house_name, races[race_name], start_year, False, founders[house_name]))

    return world

# --- Main Simulation Function ---
def simulate_years(world : World, end_year: int):
    for year in range(world.current_year, end_year + 1):
        # make everyone one year older as the year is over
        world.advance_year()
        # living_people : list[Person] = world.get_alive_people()
        generate_deaths(world)
        generate_births(world)
        generate_marriages(world)


world = generate_world(0)
simulate_years(world, 250)
world.events.sort(key=lambda e: e.year)
for event in world.events:
    print(f"{event.year} : {event.description}")


# counts = defaultdict(int)
# for person in world.people.values():
#     if person.gender == Gender.FEMALE and person.is_married:
#         print(person, person.age, len(person.family.children))
#         counts[len(person.family.children)] +=1
# print(counts)
# print(len(world.get_alive_people()))