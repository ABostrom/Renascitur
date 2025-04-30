from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict

@dataclass
class StatValue:
    value: int
    min_value: int = 0
    max_value: int = 100

    def add(self, amount: int):
        self.value = max(self.min_value, min(self.value + amount, self.max_value))

    def set(self, value: int):
        self.value = max(self.min_value, min(value, self.max_value))

    def __int__(self):
        return self.value

    def __iadd__(self, amount: int):
        self.add(amount)
        return self

    def __str__(self):
        return str(self.value)

@dataclass
class StatBlock:
    stats: Dict[str, StatValue] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, template: dict[str, tuple[int, int, int]]) -> StatBlock:
        block = cls()
        for name, (val, minv, maxv) in template.items():
            block.stats[name] = StatValue(val, minv, maxv)
        return block

    def add_stat(self, name: str, initial: int = 0, min_value: int = 0, max_value: int = 100):
        self.stats[name] = StatValue(initial, min_value, max_value)

    def __getitem__(self, name: str) -> int:
        return int(self.stats[name])

    def __setitem__(self, name: str, value: int):
        self.stats[name].set(value)

    def __iadd__(self, other: Dict[str, int]):
        for key, val in other.items():
            if key in self.stats:
                self.stats[key] += val
        return self

    def __repr__(self):
        return str({k: int(v) for k, v in self.stats.items()})

