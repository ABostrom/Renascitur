"""Run recipes: a TOML file that says exactly how to produce a run.

    [run]
    name = "toy-baseline"
    engine = "0.1.0"            # must match the engine, or the run refuses
    seed = 1234
    world = "toy"
    end = "1X 300"              # runs to the end of that year
    checkpoint_every_years = 10

    [world]                     # world parameters, passed to the world's engine factory
    people_per_village = 100

    [[ripple]]
    id = "r1"
    kind = "protect"
    date = "1X 120"
    target = "t:Ashford-00"
    params = { until = [1, 140, 359] }

Recipes are committed to git (`recipes/`); run folders are not.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from renasci import __version__
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.worlds import get_world

RUN_KEYS = {"name", "engine", "seed", "world", "end", "checkpoint_every_years", "full_reads"}
SECTIONS = {"run", "world", "ripple"}
RIPPLE_KEYS = {"id", "kind", "date", "target", "params"}


@dataclass(frozen=True)
class Recipe:
    name: str
    seed: int
    world: str
    end: Date
    checkpoint_every_years: int
    params: dict
    ripples: tuple[Ripple, ...]
    raw: dict
    full_reads: bool = False  # keep every read row (analysis runs); otherwise one digest per scope


def parse_recipe(raw: dict) -> Recipe:
    unknown = set(raw) - SECTIONS
    if unknown:
        raise ValueError(f"unknown recipe sections: {sorted(unknown)}")
    run = raw.get("run", {})
    if set(run) - RUN_KEYS or not {"name", "engine", "seed", "world", "end"} <= set(run):
        raise ValueError(f"[run] needs {sorted(RUN_KEYS - {'checkpoint_every_years', 'full_reads'})} and allows only "
                         f"{sorted(RUN_KEYS)}; got {sorted(run)}")
    if run["engine"] != __version__:
        raise ValueError(f"recipe is for engine {run['engine']}, this is {__version__}")
    if type(run["seed"]) is not int:
        raise ValueError("seed must be an int")
    world = get_world(run["world"])
    unknown_params = set(raw.get("world", {})) - world.params
    if unknown_params:
        raise ValueError(f"unknown [world] settings for {world.name}: {sorted(unknown_params)} "
                         f"(allowed: {sorted(world.params)})")
    cal = world.calendar
    end = cal.parse(run["end"])
    end = Date(end.age, end.year, cal.days_per_year - 1)
    ripples = []
    for r in raw.get("ripple", []):
        if set(r) - RIPPLE_KEYS:
            raise ValueError(f"unknown ripple keys: {sorted(set(r) - RIPPLE_KEYS)}")
        missing = {"id", "kind", "date", "target"} - set(r)
        if missing:
            raise ValueError(f"ripple {r.get('id', '?')} is missing {sorted(missing)}")
        ripples.append(Ripple(r["id"], r["kind"], cal.parse(r["date"]), r["target"], r.get("params", {})))
    every = run.get("checkpoint_every_years", 10)
    if type(every) is not int or every < 1:
        raise ValueError("checkpoint_every_years must be a positive int")
    full_reads = run.get("full_reads", False)
    if type(full_reads) is not bool:
        raise ValueError("full_reads must be true or false")
    return Recipe(run["name"], run["seed"], run["world"], end, every, dict(raw.get("world", {})),
                  tuple(ripples), raw, full_reads)


def load_recipe(path) -> Recipe:
    with Path(path).open("rb") as f:
        return parse_recipe(tomllib.load(f))
