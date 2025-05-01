from __future__ import annotations
from renasci.events.base import Event
from renasci.events.house_events import GrumblingEvent
from renasci.generators.base import StatThresholdGenerator
from renasci.house import House

class GrumblingGenerator(StatThresholdGenerator):
    stat = "unrest"
    threshold = 30
    direction = "above"
    entity_type = House

    def create_event(self, world, entity) -> Event:
        return GrumblingEvent.create(world, entity)
