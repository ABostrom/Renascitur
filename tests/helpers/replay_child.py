"""Run in a fresh interpreter: restore a checkpoint, run to the end, print events and state hash.

    python replay_child.py <checkpoint.json.gz> <age> <year> <day> <out.json>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mini_world import CAL, RULESETS, SEED  # noqa: E402

from renasci.core.calendar import Date  # noqa: E402
from renasci.core.engine import Engine  # noqa: E402
from renasci.io.checkpoint import load_checkpoint  # noqa: E402

path, age, year, day, out = sys.argv[1:]
engine = Engine.restore(load_checkpoint(path), CAL, RULESETS, seed=SEED)
engine.run(until=Date(int(age), int(year), int(day)))
rows = engine.pending()
Path(out).write_text(json.dumps({"events": rows["events"], "hinges": rows["hinges"],
                                 "state_hash": engine.state_hash()}), encoding="utf-8")
