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
import re
from dataclasses import dataclass
from pathlib import Path

from renasci import __version__
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.worlds import get_world

RUN_KEYS = {"name", "engine", "seed", "world", "end", "checkpoint_every_years", "full_reads"}
# A run's name is its folder's name: one plain name, never a path, and nothing Windows treats specially.
RUN_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
RESERVED = re.compile(r"(con|prn|aux|nul|com[0-9]|lpt[0-9])(\..*)?", re.IGNORECASE)


def check_run_name(name) -> str:
    if not isinstance(name, str) or not RUN_NAME.fullmatch(name) or name.endswith(".") or RESERVED.fullmatch(name):
        raise ValueError(f"[run] name must be a plain folder name (letters, digits, . _ -; at most 64), got {name!r}")
    return name
SECTIONS = {"run", "world", "ripple", "vault", "reshuffle"}
RESHUFFLE_KEYS = {"from", "salt"}
VAULT_KEYS = {"path"}
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
    vault: dict | None = None  # {"path": ...}: cast the vault's canon into the run (S2 §7)
    reshuffles: tuple = ()  # ((from: Date, salt), ...): re-roll everything from the start of `from`'s quarter

    def rng_reshuffles(self, calendar) -> tuple:
        from renasci.core.rng import Reshuffle

        return tuple(Reshuffle(calendar.canonical_tick(d), salt) for d, salt in self.reshuffles)


def parse_recipe(raw: dict) -> Recipe:
    unknown = set(raw) - SECTIONS
    if unknown:
        raise ValueError(f"unknown recipe sections: {sorted(unknown)}")
    run = raw.get("run", {})
    if set(run) - RUN_KEYS or not {"name", "engine", "seed", "world", "end"} <= set(run):
        raise ValueError(f"[run] needs {sorted(RUN_KEYS - {'checkpoint_every_years', 'full_reads'})} and allows only "
                         f"{sorted(RUN_KEYS)}; got {sorted(run)}")
    check_run_name(run["name"])
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
    reshuffles = []
    for r in raw.get("reshuffle", []):
        if not isinstance(r, dict) or set(r) != RESHUFFLE_KEYS or not isinstance(r["salt"], str) or not r["salt"]:
            raise ValueError('a [[reshuffle]] is from = "<date>" and salt = "<any text>"')
        d = cal.parse(r["from"])
        q = cal.canonical_tick(d)[2]
        start = Date(d.age, d.year, -(-q * cal.days_per_year // 4))  # (the start of its quarter: what's re-rolled)
        reshuffles.append((start, r["salt"]))
    every = run.get("checkpoint_every_years", 10)
    if type(every) is not int or every < 1:
        raise ValueError("checkpoint_every_years must be a positive int")
    full_reads = run.get("full_reads", False)
    if type(full_reads) is not bool:
        raise ValueError("full_reads must be true or false")
    vault = raw.get("vault")
    if vault is not None and (not isinstance(vault, dict) or set(vault) != VAULT_KEYS or not isinstance(vault["path"], str)):
        raise ValueError('[vault] is path = "<the vault folder>"')
    if vault is not None and world.scenario is None:
        raise ValueError(f"the {world.name} world has no people to cast canon into")
    return Recipe(run["name"], run["seed"], run["world"], end, every, dict(raw.get("world", {})),
                  tuple(ripples), raw, full_reads, dict(vault) if vault else None, tuple(reshuffles))


def load_recipe(path) -> Recipe:
    """A recipe file; a relative [vault] path is relative to the recipe, not to where it's run from."""
    with Path(path).open("rb") as f:
        recipe = parse_recipe(tomllib.load(f))
    if recipe.vault and not Path(recipe.vault["path"]).is_absolute():
        resolved = {"path": str((Path(path).parent / recipe.vault["path"]).resolve())}
        object.__setattr__(recipe, "vault", resolved)
    return recipe
