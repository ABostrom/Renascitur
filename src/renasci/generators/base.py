from __future__ import annotations
from typing import Iterator, Literal
from renasci.events.base import Event

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

class EventGenerator():
    def generate(self, world: World) -> Iterator[Event]:
        pass


class CoreEventGenerator(EventGenerator):
    pass


class StatThresholdGenerator(EventGenerator):
    stat: str
    threshold: int
    direction: Literal["above", "below"]
    entity_type: type

    def generate(self, world: World) -> Iterator[Event]:
        for delta in world.current_context.changed_stats.values():
            if not isinstance(delta.entity, self.entity_type):
                continue
            if delta.stat != self.stat:
                continue

            if self.direction == "above" and delta.after >= self.threshold:
                yield self.create_event(world, delta.entity)
            elif self.direction == "below" and delta.after <= self.threshold:
                yield self.create_event(world, delta.entity)

    def create_event(self, world, entity) -> Event:
        pass