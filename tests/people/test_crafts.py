"""Materials, crafting and masterworks (S9 spec §3, #124): towns yield materials into stock on an exact goods
ledger; a skilled maker sometimes makes a masterwork, an object with a maker, a material and a first owner."""

import copy

import pytest

from renasci import kin
from renasci.core.calendar import Date
from renasci.people import crafts

CATALOGUE = {
    "jobs": {
        "farmer": {"name": "farmer", "demand": 0.5, "income": 1.0},
        "miner": {"name": "miner", "demand": 0.2, "income": 1.5},
        "smith": {"name": "smith", "demand": 0.3, "income": 3.0, "makes": ["blade"]},
    },
    "materials": {
        "food": {"name": "food", "by": ["farmer"], "yield": {"*": 2.0}, "value": 1},
        "iron": {"name": "iron", "by": ["miner"], "yield": {"*": 0.5}, "value": 4},
    },
    "types": {"blade": {"name": "blade", "material": "iron", "cost": 3}},
    "master_rate": 2.0,  # (pinned high: every skilled smith tries)
}


def world(catalogue=CATALOGUE, years=15, seed=4):
    sc = copy.deepcopy(kin.SCENARIO)
    if catalogue is not None:
        sc["params"]["crafts"] = catalogue
    e = kin.new_engine(seed=seed, scenario=sc)
    e.run(until=Date(1, years, 359))
    return e


@pytest.fixture(scope="module")
def made():
    return world()


def col(e, name, s):
    return int(e.store.read_column(name, [s])[0])


def test_towns_yield_materials_into_stock(made):
    for s in made.store.ids("settlement"):
        assert col(made, "goods:food:produced", s) > 0
        assert col(made, "stock:food", s) > 0


def test_the_goods_ledger_balances_exactly(made):
    for s in made.store.ids("settlement"):
        for m in CATALOGUE["materials"]:
            assert crafts.balance(made.store, s, m) == 0, (s, m)


def test_a_skilled_smith_makes_a_masterwork_and_it_finds_an_owner(made):
    objs = made.store.ids("object")
    assert objs
    for o in objs:
        maker, owner = made.store.get(o, "maker"), made.store.get(o, "owner")
        assert made.store.get(maker, "job") == "smith"
        assert made.store.get(o, "type") == "blade" and made.store.get(o, "material") == "iron"
        assert 0 < made.store.get(o, "quality") <= 1
        assert owner and made.store.kind(owner) == "person"
    first = next(x for x in made.events if x.type == "object.made")
    given = next(x for x in made.events if x.type == "object.given" and x.roles["object"] == first.roles["object"])
    assert given.date == first.date


def test_a_masterwork_uses_its_material(made):
    used = sum(col(made, "goods:iron:used", s) for s in made.store.ids("settlement"))
    assert used == CATALOGUE["types"]["blade"]["cost"] * len(made.store.ids("object"))


def test_at_most_one_masterwork_a_town_a_year(made):
    seen = {}
    for x in made.events:
        if x.type == "object.made":
            key = (x.place, x.date.year)
            assert key not in seen, key
            seen[key] = x


def test_a_trickle_still_yields_its_fractions_add_up():
    cat = copy.deepcopy(CATALOGUE)
    cat["materials"]["gem"] = {"name": "gem", "by": ["miner"], "yield": {"*": 0.003}, "value": 9}
    e = world(catalogue=cat, years=12)
    assert sum(col(e, "goods:gem:produced", s) for s in e.store.ids("settlement")) > 0


def test_a_buyer_pays_no_more_than_they_have_and_coin_is_kept(made):
    for x in made.events:
        if x.type == "object.given" and x.roles.get("giver"):
            assert x.payload["price"] >= 0
    assert all(float(made.store.get(p, "wealth") or 0) >= 0 for p in made.store.ids("person"))


def test_no_crafts_no_goods():
    e = world(catalogue=None, years=2)
    assert not e.store.ids("object") and not any(c.startswith(("stock:", "goods:")) for c in e.store._columns)


def test_jobs_without_materials_still_work():
    e = world(catalogue={"jobs": CATALOGUE["jobs"]}, years=3)
    assert not e.store.ids("object") and not any(c.startswith("stock:") for c in e.store._columns)


def test_a_catalogue_s_materials_and_types_are_checked():
    from renasci.people.work import check

    bad = copy.deepcopy(CATALOGUE)
    bad["types"]["blade"]["material"] = "mithril"
    with pytest.raises(ValueError):
        check(bad)
    bad = copy.deepcopy(CATALOGUE)
    bad["materials"]["iron"]["by"] = ["wizard"]
    with pytest.raises(ValueError):
        check(bad)
