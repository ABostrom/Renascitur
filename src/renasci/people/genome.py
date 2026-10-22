"""Genomes: which variants a person carries, where each copy came from, and what they make of them.

A **catalogue** (world data, JSON) lists the loci. Each locus has variants, a model for how its two
copies show, a mutation rate, and the traits it moves. **Groups** give founder frequencies (a race,
a region, a lineage), and must cover every locus.

A genome is plain JSON, `{locus: [copy, copy]}`: the mother's copy first, then the father's. A copy
is `"variant@origin"`. The origin is `f:<group or settlement>` for founder stock, or the id of the
birth event in which it mutated. Copies keep their origin as they pass down, which is what lets the
Observatory show where an allele entered a bloodline.

**Draws.** Every (locus, parent slot) draws from its own keyed stream, `streams(name)`, and always
takes exactly three numbers: which copy (or which variant, for an unknown parent), whether it
mutates, and what it mutates to. So adding a locus, or changing one locus's mutation rate, never
changes what any other locus inherits. In the engine `streams` is
`lambda name: ctx.rng(f"meiosis:{name}", child)`; `keyed(key)` makes one from a plain key (tests).
Everything here is pure: no store, no context.

Models:
- `dominant`: the first variant in `order` that is present shows; its effects apply once.
- `additive`: both copies' effects add.
- `threshold`: the copies' effects add; the locus adds `amount` (default 1) to each of its traits
  when that sum reaches `threshold` (required), else nothing (a gift that needs enough of a bloodline).

A trait is `base + sum of loci + sum of environment[name] * coefficient`, clipped to `range` when
the catalogue gives one. Every trait a locus moves must be declared in the catalogue's `traits`.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from renasci.core.canon import canonical
from renasci.core.rng import Stream

MODELS = ("dominant", "additive", "threshold")


def allele(variant: str, origin: str) -> str:
    return f"{variant}@{origin}"


def variant_of(copy: str) -> str:
    return copy.split("@", 1)[0]


def origin_of(copy: str) -> str:
    return copy.split("@", 1)[1]


def keyed(key: int):
    """Named sub-streams derived from one integer key (for tests and tools outside a ctx)."""
    def streams(name: str) -> Stream:
        digest = hashlib.blake2b(f"{key}|{name}".encode(), digest_size=8).digest()
        return Stream(int.from_bytes(digest, "big"))
    return streams


def _number(label: str, value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a number, got {value!r}")
    return float(value)


@dataclass(frozen=True)
class Locus:
    id: str
    variants: tuple[str, ...]
    model: str
    order: tuple[str, ...]
    mutation: float
    traits: dict  # {trait: {variant: effect}}, effects as floats
    threshold: float = 0.0
    amount: float = 1.0

    def __hash__(self):
        return hash(self.id)


def _check_freqs(label: str, freqs: dict, loci) -> dict:
    """Frequencies for every locus, each over known variants, non-negative, summing to 1 (as floats)."""
    missing = [lo.id for lo in loci if lo.id not in freqs]
    if missing:
        raise ValueError(f"{label}: frequencies must cover every locus (missing {missing})")
    by_id = {lo.id: lo for lo in loci}
    out = {}
    for lid, fr in freqs.items():
        if lid not in by_id:
            raise ValueError(f"{label}: unknown locus {lid}")
        if set(fr) - set(by_id[lid].variants):
            raise ValueError(f"{label}, locus {lid}: unknown variant {sorted(set(fr) - set(by_id[lid].variants))}")
        fr = {v: _number(f"{label}, locus {lid}, {v}", p) for v, p in fr.items()}
        if any(p < 0 for p in fr.values()) or not math.isclose(sum(fr.values()), 1.0, abs_tol=1e-9):
            raise ValueError(f"{label}, locus {lid}: frequencies must be non-negative and sum to 1")
        out[lid] = fr
    return out


@dataclass(frozen=True)
class Catalogue:
    loci: tuple[Locus, ...]
    groups: dict  # {group: {locus: {variant: frequency}}}
    traits: dict  # {trait: {"base": float, "environment": {name: coefficient}, "range": [lo, hi]}}

    def __hash__(self):  # numbers are floats after from_json, so equal catalogues hash equal
        return hash(canonical(self.to_json()))

    @classmethod
    def from_json(cls, data: dict) -> Catalogue:
        data = json.loads(canonical(data))  # a private copy
        loci = []
        seen = set()
        for raw in data.get("loci", []):
            lid = raw.get("id")
            if not isinstance(lid, str) or not lid or lid in seen:
                raise ValueError(f"locus ids must be unique non-empty strings, got {lid!r}")
            seen.add(lid)
            variants = tuple(raw.get("variants", ()))
            if len(variants) < 2 or len(set(variants)) != len(variants) or not all(isinstance(v, str) and v for v in variants):
                raise ValueError(f"locus {lid}: variants must be at least two distinct names")
            if any("@" in v for v in variants):
                raise ValueError(f"locus {lid}: variant names can't contain '@' (it separates the origin)")
            model = raw.get("model")
            if model not in MODELS:
                raise ValueError(f"locus {lid}: model must be one of {MODELS}, got {model!r}")
            order = tuple(raw.get("order", variants))
            if sorted(order) != sorted(variants):
                raise ValueError(f"locus {lid}: order must list each variant once")
            rate = raw.get("mutation", 0.0)
            if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not 0 <= rate <= 1:
                raise ValueError(f"locus {lid}: mutation must be a probability, got {rate!r}")
            traits = {}
            for trait, effects in raw.get("traits", {}).items():
                unknown = set(effects) - set(variants)
                if unknown:
                    raise ValueError(f"locus {lid}: trait {trait} names an unknown variant {sorted(unknown)}")
                traits[trait] = {v: _number(f"locus {lid}, trait {trait}, {v}", e) for v, e in effects.items()}
            if model == "threshold" and "threshold" not in raw:
                raise ValueError(f"locus {lid}: a threshold locus needs a threshold")
            loci.append(Locus(lid, variants, model, order, float(rate), traits,
                              _number(f"locus {lid} threshold", raw.get("threshold", 0.0)),
                              _number(f"locus {lid} amount", raw.get("amount", 1.0))))
        groups = {name: _check_freqs(f"group {name}", freqs, loci) for name, freqs in data.get("groups", {}).items()}
        traits = {}
        for name, spec in data.get("traits", {}).items():
            out = {"base": _number(f"trait {name} base", spec.get("base", 0.0)),
                   "environment": {k: _number(f"trait {name} environment coefficient {k}", c)
                                   for k, c in spec.get("environment", {}).items()}}
            if "range" in spec:
                r = spec["range"]
                if (not isinstance(r, list) or len(r) != 2
                        or _number(f"trait {name} range", r[0]) > _number(f"trait {name} range", r[1])):
                    raise ValueError(f"trait {name}: range must be [low, high] with low <= high")
                out["range"] = [float(r[0]), float(r[1])]
            traits[name] = out
        undeclared = sorted({t for lo in loci for t in lo.traits} - set(traits))
        if undeclared:
            raise ValueError(f"traits used by loci must be declared in the catalogue's traits: {undeclared}")
        return cls(tuple(loci), groups, traits)

    def to_json(self) -> dict:
        loci = [{"id": lo.id, "variants": list(lo.variants), "model": lo.model, "order": list(lo.order),
                 "mutation": lo.mutation, "traits": lo.traits, "threshold": lo.threshold, "amount": lo.amount}
                for lo in self.loci]
        return json.loads(canonical({"loci": loci, "groups": self.groups, "traits": self.traits}))


def _pick(u: float, freqs: dict, variants: tuple[str, ...]) -> str:
    """The variant at `u` in [0, 1) on the cumulative frequencies, in the locus's variant order."""
    weights = [freqs.get(v, 0.0) for v in variants]
    target, running = u * sum(weights), 0.0
    for v, w in zip(variants, weights):
        running += w
        if target < running:
            return v
    return next(v for v, w in zip(reversed(variants), reversed(weights)) if w > 0)


def _draw3(streams, name: str) -> tuple[float, float, float]:
    """The fixed budget of one (locus, slot): choose, mutate?, mutate to."""
    s = streams(name)
    return float(s.random()), float(s.random()), float(s.random())


def _mutate(lo: Locus, copy: str, u_mut: float, u_to: float, birth: str, mutations: list) -> str:
    if u_mut >= lo.mutation:
        return copy
    others = [v for v in lo.variants if v != variant_of(copy)]
    mutations.append(lo.id)
    return allele(others[min(int(u_to * len(others)), len(others) - 1)], birth)


def founder(cat: Catalogue, group: str, streams, origin: str) -> dict:
    """A founder genome drawn from a group's frequencies; every copy gets `origin`."""
    freqs = cat.groups[group]
    return {lo.id: [allele(_pick(_draw3(streams, f"{lo.id}/{slot}")[0], freqs[lo.id], lo.variants), origin)
                    for slot in ("0", "1")]
            for lo in cat.loci}


def inherit(cat: Catalogue, mother: dict | None, father: dict | None, streams, birth: str,
            unknown: tuple[dict, str] | None = None) -> tuple[dict, list[str]]:
    """A child's genome: one copy from each parent per locus, then mutation.

    A parent may be None (unknown): its copy is drawn from `unknown = (frequencies, origin)`.
    Returns the genome and the loci where a copy mutated (once per mutated copy). A mutated copy's
    origin is `birth`, the birth event's id.
    """
    if (mother is None or father is None) and unknown is None:
        raise ValueError("an unknown parent needs frequencies to draw from")
    freqs = _check_freqs("unknown-parent frequencies", unknown[0], cat.loci) if unknown else None
    child: dict = {}
    mutations: list[str] = []
    for lo in cat.loci:
        pair = []
        for slot, parent in (("m", mother), ("f", father)):
            u_choose, u_mut, u_to = _draw3(streams, f"{lo.id}/{slot}")
            if parent is None:
                copy = allele(_pick(u_choose, freqs[lo.id], lo.variants), unknown[1])
            else:
                copy = parent[lo.id][0 if u_choose < 0.5 else 1]
            pair.append(_mutate(lo, copy, u_mut, u_to, birth, mutations))
        child[lo.id] = pair
    return child, mutations


def phenotype(cat: Catalogue, genome: dict, environment: dict) -> dict[str, float]:
    """Traits from a genome and an environment. Pure: the same inputs always give the same traits."""
    values = {t: spec["base"] for t, spec in cat.traits.items()}
    for lo in cat.loci:
        present = [variant_of(c) for c in genome[lo.id]]
        for trait, effects in lo.traits.items():
            if lo.model == "dominant":
                shown = next(v for v in lo.order if v in present)
                add = effects.get(shown, 0.0)
            elif lo.model == "additive":
                add = sum(effects.get(v, 0.0) for v in present)
            else:  # threshold
                add = lo.amount if sum(effects.get(v, 0.0) for v in present) >= lo.threshold else 0.0
            values[trait] += add
    for trait, spec in cat.traits.items():
        for name, coefficient in sorted(spec["environment"].items()):
            values[trait] += coefficient * float(environment.get(name, 0.0))
        if "range" in spec:
            low, high = spec["range"]
            values[trait] = min(max(values[trait], low), high)
    return values
