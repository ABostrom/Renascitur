from dataclasses import dataclass, field

from renasci.events.base import Event, EventBus
from renasci.events.person_events import SuccessionEvent, WidowEvent
from renasci.house import House
from renasci.person import Person


@dataclass
class World:
    current_year: int
    people: dict[str, Person] = field(default_factory=dict)
    houses: dict[str, House] = field(default_factory=dict)
    events: list[Event] = field(default_factory=list)
    event_bus: EventBus = field(default_factory=EventBus)

    def __post_init__(self):
        self.register_event_types()

    def register_event_types(self):
        self.event_bus.register_event_type(SuccessionEvent)
        self.event_bus.register_event_type(WidowEvent)

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
    