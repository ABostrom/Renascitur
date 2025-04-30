from __future__ import annotations
from dataclasses import dataclass


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

class EventBus:
    def __init__(self):
        self.event_types: list[type[Event]] = []

    def register_event_type(self, event_cls: type[Event]):
        self.event_types.append(event_cls)

    def publish(self, event: Event):
        event.apply()

        for event_cls in self.event_types:
            new_event = event_cls.should_create_from(event)
            if new_event:
                self.publish(new_event)


@dataclass
class Event:
    year: int
    type: str
    description: str
    world: World

    def __post_init__(self) :
        self.world.events.append(self)

    def __str__(self):
        return self.type

    def __repr__(self):
        return str(self)

    def apply(self):
        pass

    @classmethod
    def should_create_from(cls, cause_event: Event) -> Event | None:
        return None  