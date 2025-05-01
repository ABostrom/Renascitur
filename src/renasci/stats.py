from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from renasci.world import World

@dataclass
class StatDelta:
    entity: Any  # Person, House, etc.
    stat: str
    before: int
    after: int

    def net_change(self) -> int:
        return self.after - self.before

    def is_increase(self) -> bool:
        return self.after > self.before

    def is_decrease(self) -> bool:
        return self.after < self.before

    def was_modified(self) -> bool:
        return self.before != self.after

    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return f"{self.stat}:[{self.before}|{self.after}]"

@dataclass
class StatValue:
    name: str
    value: int
    min_value: int
    max_value: int
    world: World
    owner: Any

    def add(self, amount: int):
        old = self.value
        self.value = max(self.min_value, min(self.value + amount, self.max_value))
        self._record_change(old, self.value)

    def set(self, value: int):
        old = self.value
        self.value = max(self.min_value, min(value, self.max_value))
        self._record_change(old, self.value)

    def _record_change(self, old: int, new: int):
        if old != new:
            delta = StatDelta(entity=self.owner, stat=self.name, before=old, after=new)
            self.world.current_context.record_stat_change(delta)

    def __iadd__(self, amount: int):
        self.add(amount)
        return self

    def __int__(self):
        return self.value

    def __str__(self):
        return str(self.value)



@dataclass
class StatBlock:
    world: World
    owner: Any = None
    stats: Dict[str, StatValue] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, owner: Any, world : World, template: dict[str, tuple[int, int, int]]) -> StatBlock:
        block = cls(world=world, owner=owner)
        for name, (val, minv, maxv) in template.items():
            block.stats[name] = StatValue(
                name=name,
                value=val,
                min_value=minv,
                max_value=maxv,
                world=world,
                owner=owner,
            )
        return block
    
    def __getitem__(self, name: str) -> int:
        return self.stats[name].value
    
    def __setitem__(self, name: str, value: int):
        self.stats[name].set(value)

    def __iadd__(self, updates: Dict[str, int]):
        for key, value in updates.items():
            if key in self.stats:
                self.stats[key] += value
        return self

    def __contains__(self, key: str) -> bool:
        return key in self.stats

    def keys(self):
        return self.stats.keys()

    def items(self):
        return self.stats.items()

    def values(self):
        return self.stats.values()


