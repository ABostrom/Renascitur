from dataclasses import dataclass, field

from renasci.context import WorldContext
from renasci.events.base import Event, EventBus
from renasci.events.person_events import SuccessionEvent, WidowEvent
from renasci.generators.base import CoreEventGenerator, EventGenerator, StatThresholdGenerator
from renasci.generators.births import BirthGenerator
from renasci.generators.deaths import DeathGenerator
from renasci.generators.marriages import MarriageGenerator
from renasci.generators.stats import GrumblingGenerator
from renasci.house import House
from renasci.person import Person
from renasci.stats import StatBlock


DEFAULT_WORLD_STATS = {
            "stability": (75, 0, 100),
            "danger": (10, 0, 100),
            "prosperity": (50, 0, 100),
            "tension": (25, 0, 100),
        }

@dataclass
class World():
    id : str
    current_year: int
    people: dict[str, Person] = field(default_factory=dict)
    houses: dict[str, House] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    generators : list[EventGenerator] = field(default_factory=list)
    event_bus: EventBus = field(default_factory=EventBus)
    stats : StatBlock = field(init=False)

    def __post_init__(self):
        self.stats = StatBlock.from_dict(self,self,DEFAULT_WORLD_STATS)
        self.register_event_types()
        self.register_generator_types()

    def register_event_types(self):
        self.event_bus.register_event_type(SuccessionEvent)
        self.event_bus.register_event_type(WidowEvent)

    def register_generator_types(self):
        self.generators.extend([
            BirthGenerator(),
            MarriageGenerator(),
            DeathGenerator(),
            GrumblingGenerator()
        ])

    def advance_year(self):
        self.current_context = WorldContext(year=self.current_year)

        # 1. People age
        for person in self.get_alive_people():
            person.life.age += 1

        for generator in self.generators:
            if isinstance(generator, CoreEventGenerator):
                for event in generator.generate(self):
                    self.event_bus.publish(event)

        for generator in self.generators:
            if isinstance(generator, StatThresholdGenerator):
                for event in generator.generate(self):
                    self.event_bus.publish(event)

        self.current_year += 1


    def add_people(self, people : list[Person]):
        for person in people : self.add_person(person)

    def add_person(self, person: Person):
        self.people[person.id] = person

    def add_house(self, house: House):
        self.houses[house.id] = house

    def add_event(self, event: Event):
        self.events.append(event)

    def get_alive_people(self) -> list[Person]:
        return [p for p in self.people.values() if p.is_alive]
    
    def __hash__(self) -> int:
        return hash(self.id)
    
    def __str__(self) -> str:
        return str(f"year: {self.current_year}")

    def __repr__(self) -> str:
        return str(self)
    