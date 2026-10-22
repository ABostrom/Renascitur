"""Genomes: which variants a person carries, where each copy came from, and what they make of them.

A **catalogue** (world data, JSON) lists the loci. Each locus has variants, a model for how its two
copies show, a mutation rate, and the traits it moves. **Groups** give founder frequencies (a race,
a region, a lineage).

A genome is plain JSON, `{locus: [copy, copy]}`: the mother's copy first, then the father's. A copy
is `"variant@origin"`. The origin is `f:<group or settlement>` for founder stock, or the id of the
birth event in which it mutated. Copies keep their origin as they pass down, which is what lets the
Observatory show where an allele entered a bloodline.

Draws come from a keyed `Stream` (one per child, owned by the child), in catalogue order, so the
same inputs always give the same child. Everything here is pure: no store, no context.

Models:
- `dominant`: the first variant in `order` that is present shows; its effects apply once.
- `additive`: both copies' effects add.
- `threshold`: the copies' effects add; the locus adds `amount` (default 1) to each of its traits
  when that sum reaches `threshold`, else nothing (a gift that needs enough of a bloodline).

A trait is `base + sum of loci + sum of environment[name] * coefficient`, clipped to `range` when
the catalogue gives one.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

from renasci.core.canon import canonical

MODELS = ("dominant", "additive", "threshold")


def allele(variant: str, origin: str) -> str:
    return f"{variant}@{origin}"


def variant_of(copy: str) -> str:
    return copy.split("@", 1)[0]


def origin_of(copy: str) -> str:
    return copy.split("@", 1)[1]


@dataclass(frozen=True)
class Locus:
    id: str
    variants: tuple[str, ...]
    model: str
    order: tuple[str, ...]
    mutation: float
    traits: dict  # {trait: {variant: effect}}
    threshold: float = 0.0
    amount: float = 1.0

    def __hash__(self):
        return hash(self.id)


@dataclass(frozen=True)
class Catalogue:
    loci: tuple[Locus, ...]
    groups: dict  # {group: {locus: {variant: frequency}}}
    traits: dict  # {trait: {"base": float, "environment": {name: coefficient}, "range": [lo, hi]}}

    def __hash__(self):
        return hash(canonical(self.to_json()))

    @classmethod
    def from_json(cls, data: dict) -> Catalogue:
        data = json.loads(canonical(data))  # a private copy, numbers normalised
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
            if not isinstance(rate, (int, float)) or not 0 <= rate <= 1:
                raise ValueError(f"locus {lid}: mutation must be a probability, got {rate!r}")
            traits = raw.get("traits", {})
            for trait, effects in traits.items():
                unknown = set(effects) - set(variants)
                if unknown:
                    raise ValueError(f"locus {lid}: trait {trait} names an unknown variant {sorted(unknown)}")
            loci.append(Locus(lid, variants, model, order, float(rate), traits,
                              float(raw.get("threshold", 0.0)), float(raw.get("amount", 1.0))))
        by_id = {lo.id: lo for lo in loci}
        groups = data.get("groups", {})
        for name, freqs in groups.items():
            for lid, fr in freqs.items():
                if lid not in by_id:
                    raise ValueError(f"group {name}: unknown locus {lid}")
                if set(fr) - set(by_id[lid].variants):
                    raise ValueError(f"group {name}, locus {lid}: unknown variant {sorted(set(fr) - set(by_id[lid].variants))}")
                if any(p < 0 for p in fr.values()) or not math.isclose(sum(fr.values()), 1.0, abs_tol=1e-9):
                    raise ValueError(f"group {name}, locus {lid}: frequencies must be non-negative and sum to 1")
        return cls(tuple(loci), groups, data.get("traits", {}))

    def to_json(self) -> dict:
        loci = [{"id": lo.id, "variants": list(lo.variants), "model": lo.model, "order": list(lo.order),
                 "mutation": lo.mutation, "traits": lo.traits, "threshold": lo.threshold, "amount": lo.amount}
                for lo in self.loci]
        return json.loads(canonical({"loci": loci, "groups": self.groups, "traits": self.traits}))


def _pick(stream, freqs: dict, variants: tuple[str, ...]) -> str:
    """A variant drawn from frequencies, in the locus's variant order (never dict order)."""
    return variants[stream.choice_index([freqs.get(v, 0.0) for v in variants])]


def founder(cat: Catalogue, group: str, stream, origin: str) -> dict:
    """A founder genome drawn from a group's frequencies; every copy gets `origin`."""
    freqs = cat.groups[group]
    return {lo.id: [allele(_pick(stream, freqs[lo.id], lo.variants), origin) for _ in range(2)] for lo in cat.loci}


def inherit(cat: Catalogue, mother: dict | None, father: dict | None, stream, birth: str,
            unknown: tuple[dict, str] | None = None) -> tuple[dict, list[str]]:
    """A child's genome: one copy from each parent per locus, then mutation.

    A parent may be None (unknown): its copy is drawn from `unknown = (frequencies, origin)`.
    Returns the genome and the loci where a copy mutated (once per mutated copy). A mutated copy's
    origin is `birth`, the birth event's id.
    """
    child: dict = {}
    mutations: list[str] = []
    for lo in cat.loci:
        pair = []
        for parent in (mother, father):
            if parent is None:
                if unknown is None:
                    raise ValueError("an unknown parent needs frequencies to draw from")
                freqs, origin = unknown
                copy = allele(_pick(stream, freqs[lo.id], lo.variants), origin)
            else:
                copy = parent[lo.id][0 if stream.random() < 0.5 else 1]
            if lo.mutation and stream.random() < lo.mutation:
                others = [v for v in lo.variants if v != variant_of(copy)]
                copy = allele(others[stream.choice_index([1.0] * len(others))], birth)
                mutations.append(lo.id)
            pair.append(copy)
        child[lo.id] = pair
    return child, mutations


def phenotype(cat: Catalogue, genome: dict, environment: dict) -> dict[str, float]:
    """Traits from a genome and an environment. Pure: the same inputs always give the same traits."""
    values = {t: float(spec.get("base", 0.0)) for t, spec in cat.traits.items()}
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
            values[trait] = values.get(trait, 0.0) + add
    for trait, spec in cat.traits.items():
        for name, coefficient in sorted(spec.get("environment", {}).items()):
            values[trait] += coefficient * float(environment.get(name, 0.0))
        if "range" in spec:
            lo_, hi = spec["range"]
            values[trait] = min(max(values[trait], lo_), hi)
    return values
