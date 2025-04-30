from __future__ import annotations
import random
from typing import Iterator
from renasci.generators.base import EventGenerator
from renasci.events.person_events import DeathEvent
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

class DeathGenerator(EventGenerator):
    def generate(self, world: World) -> Iterator[DeathEvent]:
        for person in world.get_alive_people():
            if person.is_immortal:
                continue
            if random.random() < person.race.death_chance(person.age):
                yield DeathEvent.create(world, person)
