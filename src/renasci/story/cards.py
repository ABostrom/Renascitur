"""Cards: a person, a thing or a town with a real past, found in a finished run (#165).

`renasci gen person --run runs/m4 --house medani --age 30-50` finds what fits and writes a card: who they are, their
kin, what they've become, what they want, who hates them, what they carry, and what happened to them. It generates
nothing out of thin air: a thing worth having has a past. All of it comes from the run, and `history` and `marks` cite
the event behind each line; the rest (kin, wants, place) is the state the run ended in, not yet cited. A life can be
long, so `history` keeps its first and last lines, without the talk, and `told` says how many there were.

Picking is seeded and depends on nothing else: the same run, filters and seed give the same cards. Filters take a
short name (`--race dwarf` for `r:dwarf`). `--age` is the living's age where the run ends, `30-50` or `30-` or `30`, so
it leaves out the dead; ask for them with `--status dead`. When nothing fits, the answer says which filter to loosen and
how many that would find.

A generator is an entry in the `generators` pool: its `name`, the store `kind` it finds, the filters it `takes`, whether
one `fits`, and its `card`. An extension adds one in a file, so `renasci gen tavern` is one class; `--where key=value`
reaches its filters.
"""

from __future__ import annotations

import hashlib

from renasci.core.pools import pools
from renasci.story.text import reading

GENERATORS = pools.define("generators")
SHOWN = 12  # (the events a card tells)


def _history(run, entity: str) -> list[dict]:
    told = []
    for e in run.involves.get(entity, []):
        ev = run.by_id[e]
        line = reading(ev, run.names, run.by_id) if not ev["type"].startswith("belief.") else None
        if line:
            told.append({"date": ev["date"], "text": line, "event": ev["id"]})
    return told


def _told(run, entity: str) -> dict:
    told = _history(run, entity)
    return {"told": len(told), "history": told[:SHOWN // 2] + told[-SHOWN // 2:] if len(told) > SHOWN else told}


def _marks(f: dict) -> list[dict]:
    return [{"mark": m["id"], "since": m["since"], "event": m["event"]} for m in f.get("acquired") or []]


def named(entity_id, wanted) -> bool:
    """Does a short name (`dwarf`, `medani`) or a whole id name this id?"""
    tail = str(entity_id or "").split(":")[-1].removeprefix("house-")
    return bool(entity_id) and str(wanted) in (entity_id, tail)


def ages(text: str) -> tuple[int, float]:
    """`30-50`, `30-` or `30`."""
    lo, dash, hi = str(text).partition("-")
    if not lo.isdigit() or (hi and not hi.isdigit()) or (hi and int(hi) < int(lo)):
        raise ValueError(f"--age is like 30-50, 30- or 30, not {text!r}")
    return int(lo), (int(hi) if hi else (float("inf") if dash else int(lo)))


def number(text, flag: str) -> float:
    try:
        value = float(text)
    except (TypeError, ValueError):
        raise ValueError(f"{flag} is a number, not {text!r}") from None
    if value != value:
        raise ValueError(f"{flag} is a number, not {text!r}")
    return value


def yes(text, flag: str) -> bool:
    if str(text).lower() not in ("true", "false"):
        raise ValueError(f"{flag} is true or false, not {text!r}")
    return str(text).lower() == "true"


class Generator:
    name, kind = "", ""
    takes: tuple = ()

    def fits(self, run, entity: str, fields: dict, wants: dict) -> dict:
        """For each filter it takes: does this one pass?"""
        raise NotImplementedError

    def card(self, run, entity: str, fields: dict) -> dict:
        raise NotImplementedError


class Person(Generator):
    name, kind, takes = "person", "person", ("race", "house", "age", "job", "mark", "status")

    def fits(self, run, entity, f, wants):
        alive = run.ents[entity]["status"] != "dead"
        out = {"race": named(f.get("race"), wants.get("race")), "house": named(f.get("house"), wants.get("house")),
               "job": f.get("job") == wants.get("job"), "mark": any(m["id"] == wants.get("mark") for m in f.get("acquired") or []),
               "status": run.ents[entity]["status"] == wants.get("status")}
        if "age" in wants:
            lo, hi = ages(wants["age"])
            born = f.get("born")
            out["age"] = alive and bool(born) and lo <= run.end_year - born[1] <= hi
        return out

    def card(self, run, entity, f):
        def who(p):
            return {"id": p, "name": run.names(p)} if p else None

        ties = [run.ents[t]["fields"] for t in f.get("ties") or [] if t in run.ents]
        foes = sorted(t["b"] if t.get("a") == entity else t.get("a") for t in ties if t.get("kind") == "enemy" and not t.get("ended"))
        return {"kind": "person", "id": entity, "name": run.names.full(entity), "status": run.ents[entity]["status"],
                "born": f.get("born"), "race": f.get("race"), "sex": f.get("sex"), "house": f.get("house"), "job": f.get("job"),
                "place": f.get("place"), "traits": f.get("traits") or {}, "marks": _marks(f),
                "kin": {"mother": who(f.get("mother")), "father": who(f.get("father")), "spouse": who(f.get("spouse")),
                        "children": [who(c) for c in f.get("children") or []]},
                "wants": f.get("wants") or [], "wound": f.get("wound"), "grievances": f.get("grievances") or [],
                "enemies": [who(p) for p in foes], "carries": [{"id": o, "name": run.ents[o]["fields"].get("name"),
                                                                 "type": run.ents[o]["fields"].get("type")}
                                                                for o in f.get("possessions") or [] if o in run.ents],
                **_told(run, entity)}


class Thing(Generator):
    name, kind, takes = "object", "object", ("type", "fame", "mark", "lost")

    def fits(self, run, entity, f, wants):
        out = {"type": f.get("type") == wants.get("type"), "mark": any(m["id"] == wants.get("mark") for m in f.get("acquired") or [])}
        if "fame" in wants:
            out["fame"] = float(f.get("fame") or 0.0) >= number(wants["fame"], "--fame")
        if "lost" in wants:
            out["lost"] = bool(f.get("lost")) == yes(wants["lost"], "--lost")
        return out

    def card(self, run, entity, f):
        return {"kind": "object", "id": entity, "name": f.get("name"), "status": run.ents[entity]["status"],
                "destroyed": f.get("destroyed"), "type": f.get("type"), "material": f.get("material"),
                "quality": f.get("quality"), "fame": f.get("fame"), "maker": f.get("maker") and run.names(f["maker"]),
                "made": f.get("made"), "owner": f.get("owner") and run.names(f["owner"]), "place": f.get("place"),
                "lost": bool(f.get("lost")), "origin": f.get("origin"), "marks": _marks(f), "deeds": f.get("deeds") or [],
                **_told(run, entity)}


class Village(Generator):
    name, kind, takes = "village", "settlement", ("region", "mark")

    def fits(self, run, entity, f, wants):
        return {"region": named(f.get("region"), wants.get("region")),
                "mark": any(m["id"] == wants.get("mark") for m in f.get("acquired") or [])}

    def card(self, run, entity, f):
        return {"kind": "settlement", "id": entity, "name": run.names(entity), "region": f.get("region"), "race": f.get("race"),
                "control": f.get("control"), "residents": len(f.get("residents") or []), "marks": _marks(f),
                "immunity": f.get("immunity") or {}, "razed": f.get("razed"), "people": [
                    {"id": p, "name": run.names(p)} for p in sorted(f.get("residents") or [])[:8]],
                **_told(run, entity)}


for _g in (Person, Thing, Village):
    GENERATORS.add(_g)
GENERATORS.freeze()


def _rank(seed: int, entity: str) -> str:
    return hashlib.sha256(f"{seed}:{entity}".encode()).hexdigest()


def generate(run, generators, name: str, wants: dict, seed: int = 0, count: int = 1) -> dict:
    """Cards of a kind from a run. `wants` holds the filters given; `closest` says what loosening one would find."""
    if name not in generators:
        raise ValueError(f"no generator {name!r}; there are {sorted(generators)}")
    if count < 1:
        raise ValueError(f"--count is at least 1, not {count}")
    gen = generators[name]
    wanted = {k: v for k, v in wants.items() if v is not None}
    unknown = sorted(set(wanted) - set(gen.takes))
    if unknown:
        raise ValueError(f"{name} takes {sorted(gen.takes)}, not {unknown}")
    scored = []
    for entity, e in sorted(run.ents.items()):
        if e["kind"] == gen.kind and (gen.kind != "object" or e["status"] == "active"):  # (what's destroyed is gone)
            passed = gen.fits(run, entity, e["fields"], wanted)
            scored.append((entity, e, {k: passed[k] for k in wanted}))
    found = [(i, e) for i, e, p in scored if all(p.values())]
    found.sort(key=lambda x: _rank(seed, x[0]))
    out = {"found": len(found), "cards": [gen.card(run, i, e["fields"]) for i, e in found[:count]]}
    if not found:
        out["closest"] = {k: sum(1 for _, _, p in scored if all(v for f, v in p.items() if f != k)) for k in wanted}
    return out
