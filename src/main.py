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