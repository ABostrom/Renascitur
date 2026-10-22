from __future__ import annotations
from renasci_legacy.events.base import Event
from renasci_legacy.events.house_events import GrumblingEvent
from renasci_legacy.generators.base import StatThresholdGenerator
from renasci_legacy.house import House

class GrumblingGenerator(StatThresholdGenerator):
    stat = "unrest"
    threshold = 30
    direction = "above"
    entity_type = House

    def create_event(self, world, entity) -> Event:
        return GrumblingEvent.create(world, entity)
