from __future__ import annotations
from typing import Iterator
from renasci.events.base import Event

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

class EventGenerator():
    def generate(self, world: World) -> Iterator[Event]:
        pass
