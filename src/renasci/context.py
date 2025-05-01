from dataclasses import dataclass, field
from typing import Any

@dataclass
class StatChange:
    entity: Any  # Person, House, etc.
    stat: str
    before: int
    after: int

    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return f"{self.entity}->{self.stat}:[{self.before}|{self.after}]"

@dataclass
class WorldContext:
    year: int
    changed_stats: list[StatChange] = field(default_factory=list)


    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return f"{self.year} : {self.changed_stats}"