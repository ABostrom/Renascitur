"""Genome: catalogue, founders, inheritance with allele origins, mutation, phenotype (S3 spec §3)."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from renasci.core.rng import Stream
from renasci.people.genome import Catalogue, allele, founder, inherit, origin_of, phenotype, variant_of

CATALOGUE = {
    "loci": [
        {"id": "eye", "variants": ["brown", "blue"], "model": "dominant", "order": ["brown", "blue"],
         "mutation": 0.0, "traits": {"eye_colour": {"brown": 0.0, "blue": 1.0}}},
        {"id": "st1", "variants": ["+", "-"], "model": "additive", "mutation": 0.0,
         "traits": {"stature": {"+": 0.1, "-": -0.1}}},
        {"id": "gift", "variants": ["g", "n"], "model": "threshold", "threshold": 2, "mutation": 0.0,
         "traits": {"gift": {"g": 1, "n": 0}}},
    ],
    "groups": {
        "lowland": {"eye": {"brown": 0.8, "blue": 0.2}, "st1": {"+": 0.5, "-": 0.5}, "gift": {"g": 0.1, "n": 0.9}},
    },
    "traits": {"eye_colour": {"base": 0.0}, "stature": {"base": 0.5, "environment": {"nutrition": 0.1}},
               "gift": {"base": 0.0}},
}


@pytest.fixture
def cat():
    return Catalogue.from_json(CATALOGUE)


def g(**loci):
    """A genome from 'v@o' strings: g(eye=("blue@f:x", "brown@f:y"))."""
    return {k: list(v) for k, v in loci.items()}


def test_alleles_carry_variant_and_origin():
    a = allele("blue", "f:lowland")
    assert a == "blue@f:lowland" and variant_of(a) == "blue" and origin_of(a) == "f:lowland"


def test_founders_follow_the_group_and_are_deterministic(cat):
    genomes = [founder(cat, "lowland", Stream(k), "f:lowland") for k in range(400)]
    blue = sum(variant_of(c) == "blue" for gen in genomes for c in gen["eye"]) / 800
    assert 0.15 < blue < 0.25
    assert founder(cat, "lowland", Stream(7), "f:lowland") == founder(cat, "lowland", Stream(7), "f:lowland")
    assert all(origin_of(c) == "f:lowland" for c in genomes[0]["eye"])


def test_each_parent_gives_one_copy_with_its_origin(cat):
    mother = g(eye=("blue@m1", "blue@m2"), st1=("+@m1", "+@m2"), gift=("n@m1", "n@m2"))
    father = g(eye=("brown@f1", "brown@f2"), st1=("-@f1", "-@f2"), gift=("n@f1", "n@f2"))
    child, mutations = inherit(cat, mother, father, Stream(1), "birth1")
    assert mutations == []
    for locus in ("eye", "st1", "gift"):
        assert child[locus][0] in mother[locus] and child[locus][1] in father[locus]


def test_recessive_traits_resurface(cat):
    carrier_m = g(eye=("brown@a", "blue@b"), st1=("+@a", "+@b"), gift=("n@a", "n@b"))
    carrier_f = g(eye=("brown@c", "blue@d"), st1=("+@c", "+@d"), gift=("n@c", "n@d"))
    blue_eyed = 0
    for k in range(2000):
        child, _ = inherit(cat, carrier_m, carrier_f, Stream(k), f"b{k}")
        blue_eyed += phenotype(cat, child, {})["eye_colour"] == 1.0
    assert 0.21 < blue_eyed / 2000 < 0.29  # a quarter, from two brown-eyed carriers


def test_an_unknown_parent_is_drawn_from_frequencies(cat):
    mother = g(eye=("blue@m1", "blue@m2"), st1=("+@m1", "+@m2"), gift=("n@m1", "n@m2"))
    freqs = {"eye": {"brown": 1.0, "blue": 0.0}, "st1": {"+": 1.0, "-": 0.0}, "gift": {"g": 0.0, "n": 1.0}}
    child, _ = inherit(cat, mother, None, Stream(3), "b", unknown=(freqs, "f:Ashford"))
    assert child["eye"][1] == "brown@f:Ashford"


def test_mutation_switches_variant_and_records_the_birth(cat):
    data = {**CATALOGUE, "loci": [{**CATALOGUE["loci"][0], "mutation": 1.0}] + CATALOGUE["loci"][1:]}
    cat = Catalogue.from_json(data)
    mother = g(eye=("blue@m1", "blue@m2"), st1=("+@m1", "+@m2"), gift=("n@m1", "n@m2"))
    father = g(eye=("blue@f1", "blue@f2"), st1=("-@f1", "-@f2"), gift=("n@f1", "n@f2"))
    child, mutations = inherit(cat, mother, father, Stream(5), "birth9")
    assert child["eye"] == ["brown@birth9", "brown@birth9"]
    assert mutations == ["eye", "eye"]


def test_phenotype_models_and_environment(cat):
    homo_g = g(eye=("blue@a", "blue@b"), st1=("+@a", "+@b"), gift=("g@a", "g@b"))
    het_g = g(eye=("brown@a", "blue@b"), st1=("+@a", "-@b"), gift=("g@a", "n@b"))
    t = phenotype(cat, homo_g, {"nutrition": 1.0})
    assert t == pytest.approx({"eye_colour": 1.0, "stature": 0.5 + 0.2 + 0.1, "gift": 1.0})
    t = phenotype(cat, het_g, {})
    assert t == pytest.approx({"eye_colour": 0.0, "stature": 0.5, "gift": 0.0})


@pytest.mark.parametrize("bad, message", [
    ({"model": "lamarckian"}, "model"),
    ({"variants": ["a", "a"], "order": ["a", "a"]}, "variants"),
    ({"order": ["brown"]}, "order"),
    ({"variants": ["br@wn", "blue"], "order": ["br@wn", "blue"],
      "traits": {"eye_colour": {"br@wn": 0, "blue": 1}}}, "@"),
    ({"traits": {"eye_colour": {"green": 1}}}, "variant"),
    ({"mutation": 2}, "mutation"),
])
def test_bad_catalogues_are_refused(bad, message):
    data = {**CATALOGUE, "loci": [{**CATALOGUE["loci"][0], **bad}] + CATALOGUE["loci"][1:]}
    with pytest.raises(ValueError, match=message):
        Catalogue.from_json(data)


def test_group_frequencies_must_sum_to_one():
    data = {**CATALOGUE, "groups": {"x": {**CATALOGUE["groups"]["lowland"], "eye": {"brown": 0.5, "blue": 0.2}}}}
    with pytest.raises(ValueError, match="sum"):
        Catalogue.from_json(data)


def test_catalogue_round_trips_as_json(cat):
    assert Catalogue.from_json(cat.to_json()) == cat


# ---------------------------------------------------------------- properties

variant_names = st.text(alphabet="abcdefghij", min_size=1, max_size=3)


@st.composite
def catalogues_and_parents(draw):
    loci = []
    for n in range(draw(st.integers(1, 4))):
        variants = draw(st.lists(variant_names, min_size=2, max_size=4, unique=True))
        loci.append({"id": f"l{n}", "variants": variants, "model": draw(st.sampled_from(["dominant", "additive"])),
                     "order": variants, "mutation": draw(st.sampled_from([0.0, 0.01, 0.5])),
                     "traits": {"t": {v: float(i) for i, v in enumerate(variants)}}})
    cat = Catalogue.from_json({"loci": loci, "groups": {}, "traits": {"t": {"base": 0.0}}})

    def parent(tag):
        return {lo["id"]: [f"{draw(st.sampled_from(lo['variants']))}@{tag}{i}" for i in range(2)] for lo in loci}

    return cat, parent("m"), parent("f"), draw(st.integers(0, 2**32))


@settings(max_examples=150, deadline=None)
@given(catalogues_and_parents())
def test_every_copy_comes_from_its_parent_or_is_a_recorded_mutation(case):
    cat, mother, father, key = case
    child, mutations = inherit(cat, mother, father, Stream(key), "birth")
    assert inherit(cat, mother, father, Stream(key), "birth") == (child, mutations)  # deterministic
    mutated = 0
    for locus in cat.loci:
        for copy, parent in zip(child[locus.id], (mother, father)):
            if origin_of(copy) == "birth":
                mutated += 1
                assert variant_of(copy) in locus.variants
            else:
                assert copy in parent[locus.id]  # inherited unchanged, origin kept
    assert mutated == len(mutations)
    assert set(phenotype(cat, child, {})) == {"t"}
