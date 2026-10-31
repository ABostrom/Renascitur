"""What people believe about objects, and ripples on them (S9 spec §5, #126 slice 3): `owns` and `made`
claims, judged by the log; a planted object found in a town."""

import copy

import pytest

from renasci import kin
from renasci.analysis.truth import judge
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.people import beliefs

CATALOGUE = {
    "jobs": {
        "farmer": {"name": "farmer", "demand": 0.5, "income": 1.0},
        "miner": {"name": "miner", "demand": 0.2, "income": 1.5},
        "smith": {"name": "smith", "demand": 0.3, "income": 3.0, "makes": ["blade"]},
    },
    "materials": {"iron": {"name": "iron", "by": ["miner"], "yield": {"*": 0.5}, "value": 4}},
    "types": {"blade": {"name": "blade", "material": "iron", "cost": 3}},
    "master_rate": 2.0,
}


def world(believing=True, ripples=(), years=8, **over):
    sc = copy.deepcopy(kin.SCENARIO)
    sc["params"]["crafts"] = {**copy.deepcopy(CATALOGUE), **over}
    sc["params"]["beliefs"] = believing
    e = kin.new_engine(seed=4, scenario=sc, ripples=ripples)
    e.run(until=Date(1, years, 359))
    return e


def kinds(e, t):
    return [x for x in e.events if x.type == t]


def test_the_object_predicates():
    assert beliefs.topic(beliefs.claim("owns", object="o:1", by="p:1")) == "owns:o:1"
    assert beliefs.topic(beliefs.claim("made", object="o:1", by="p:1")) == "made:o:1"


@pytest.fixture(scope="module")
def believed():
    return world()


def test_a_masterwork_s_making_and_owner_are_seen(believed):
    seen = {x.payload["claim"]["pred"] for x in kinds(believed, "belief.perceived")}
    assert {"made", "owns"} <= seen
    made = kinds(believed, "object.made")[0]
    first = next(x for x in kinds(believed, "belief.perceived") if x.payload["claim"]["pred"] == "made")
    assert ("event", made.id) in {(c.kind, c.ref) for c in first.causes}


def test_without_beliefs_nobody_holds_object_claims():
    e = world(believing=False, years=4)
    assert kinds(e, "object.made") and not kinds(e, "belief.perceived")


def test_the_log_judges_who_owns_and_made_a_thing():
    log = [{"id": "e1", "type": "object.made", "roles": {"maker": ["p:a"], "object": ["o:1"]}, "payload": {}, "causes": []},
           {"id": "e2", "type": "object.given", "roles": {"giver": ["p:a"], "owner": ["p:b"], "object": ["o:1"]},
            "payload": {}, "causes": []},
           {"id": "e3", "type": "object.stolen", "roles": {"thief": ["p:c"], "from": ["p:b"], "object": ["o:1"]},
            "payload": {}, "causes": []}]
    assert judge(beliefs.claim("made", object="o:1", by="p:a"), log) == ("true", ["e1"])
    assert judge(beliefs.claim("owns", object="o:1", by="p:b"), log) == ("false", ["e3"])  # (it was stolen)
    assert judge(beliefs.claim("owns", object="o:1", by="p:c"), log) == ("true", ["e3"])
    assert judge(beliefs.claim("owns", object="o:9", by="p:c"), log) == ("unknown", [])


def test_a_world_refuses_what_it_cant_plant():
    thing = Ripple("r1", "plant", Date(1, 3, 10), "t:Hollow-1", {"object": {"type": "blade", "material": "iron"}})
    sc = copy.deepcopy(kin.SCENARIO)
    sc["params"]["beliefs"] = True  # (beliefs, but no crafts)
    with pytest.raises(ValueError):
        kin.new_engine(seed=4, scenario=sc, ripples=[thing])


def test_a_planted_object_turns_up_in_the_town():
    town = "t:Hollow-1"
    r = Ripple("r1", "plant", Date(1, 3, 10), town, {"object": {"type": "blade", "material": "iron", "quality": 0.9,
                                                                  "name": "the Lost Blade"}})
    e = world(ripples=[r], years=4)
    found = next(x for x in kinds(e, "object.unearthed"))
    (obj,), (finder,) = found.roles["object"], found.roles["finder"]
    assert e.store.get(obj, "name") == "the Lost Blade" and e.store.get(obj, "maker") is None
    assert found.place == town and ("ripple", "r1") in {(c.kind, c.ref) for c in found.causes}
    assert e.store.get(finder, "place") == town or e.store.status(finder) != "active"


def test_a_plant_ripple_needs_a_claim_or_an_object():
    with pytest.raises(ValueError):
        Ripple("r1", "plant", Date(1, 3, 10), "t:Hollow-1", {}).check()
    with pytest.raises(ValueError):
        Ripple("r1", "plant", Date(1, 3, 10), "t:Hollow-1", {"object": {"type": "blade"}}).check()
    with pytest.raises(ValueError):
        Ripple("r1", "plant", Date(1, 3, 10), "t:Hollow-1",
               {"object": {"type": "blade", "material": "iron", "quality": 2}}).check()
    Ripple("r1", "plant", Date(1, 3, 10), "t:Hollow-1", {"object": {"type": "blade", "material": "iron"}}).check()
