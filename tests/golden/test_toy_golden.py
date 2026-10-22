"""The toy baseline, pinned. If this changes, history changed: update it deliberately, never casually.

Things that legitimately change it: the toy ruleset, the engine's id or key schemes, the RNG, or
NumPy's draws (major.minor is pinned). Bump the engine version when they change.
"""

from renasci.core.calendar import Date
from renasci.core.canon import digest
from renasci.toy import new_engine

HISTORY = "b267882ceeb11977f389beebc5f681f4"
STATE = "28197ccc245e4bc6c164dc4921c7b560"


def test_toy_baseline_is_pinned():
    e = new_engine(people_per_village=16)
    e.run(until=Date(1, 10, 359))
    assert digest(e.pending(), size=16) == HISTORY
    assert e.state_hash() == STATE
