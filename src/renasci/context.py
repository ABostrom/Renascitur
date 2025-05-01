from dataclasses import dataclass, field
from typing import Any
from renasci.stats import StatDelta

@dataclass
class WorldContext:
    year: int
    changed_stats: dict[tuple[Any, str], StatDelta] = field(default_factory=dict)
    
    def record_stat_change(self, stat_delta : StatDelta):
        key = (stat_delta.entity, stat_delta.stat)
        
        if existing := self.changed_stats.get(key):
            self.changed_stats[key] = StatDelta(
                entity=stat_delta.entity,
                stat=stat_delta.stat,
                before=existing.before,  # preserve the earliest state
                after=stat_delta.after              # update to most recent
            )
        else:
            self.changed_stats[key] = stat_delta

    def __repr__(self):
        return str(self)
    
    def __str__(self):
        return f"{self.year} : {self.changed_stats}"