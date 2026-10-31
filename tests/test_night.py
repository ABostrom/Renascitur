"""The night (S10 §5, #130): wards fall when nobody can mend them, with nothing here naming why."""

import copy
import types

import pytest

from renasci import night, renascita
from renasci.core.calendar import Span
from renasci.core.events import Cause


def world(seed=3, years=6, **cfg):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["params"] = {**sc.get("params", {}), "night": cfg}
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


def of(e, kind):
    return [x for x in e.events if x.type == kind]


def test_a_world_without_a_night_has_none():
    e = renascita.new_engine(seed=3)
    assert not any(rs.get("night") for _, rs in e.rulesets)
    assert e.store.get(e.store.ids("settlement")[0], "wards") is None


def test_the_season_and_the_wards_set_how_dark_it_is():
    assert night.effective(0.2, 0.0, 0.0, 1.5, 0.5) == pytest.approx(0.15)
    assert night.effective(0.2, 0.0, 0.0, 1.5, 1.0) == 0.0
    assert night.effective(1.0, 1.0, 1.0, 1.5, 0.0) == 1.0


@pytest.mark.parametrize("weak", [{"people": 10}, {"ill": 0.8}, {"hunger": 1.0}, {"corpses": 400.0}])
def test_a_town_in_any_trouble_mends_less(weak):
    whole = {"people": 200, "hands": 60, "ill": 0.0, "hunger": 0.0, "corpses": 0.0}
    assert night.strength(**{**whole, **weak}) < night.strength(**whole) == 1.0


def test_an_empty_town_mends_nothing():
    assert night.strength(0, 60, 0.0, 0.0, 0.0) == 0.0


def test_the_dark_takes_a_toll_and_the_dead_are_counted():
    e = world()
    assert of(e, "night.toll")
    assert e.check_conservation() == []


def test_wards_nobody_can_mend_fail():
    e = world(mend=0.0, decay=0.2, years=3)
    failed = of(e, "ward.failed")
    assert failed and all(e.store.get(x.roles["settlement"][0], "ward_failed") == x.id for x in failed)


def test_a_town_that_can_mend_keeps_its_wards():
    assert of(world(years=3), "ward.failed") == []


class Stub:
    def __init__(self, **fields):
        self.fields, self.emitted = fields, []

    def get(self, entity, name):
        return self.fields.get(name)

    def set(self, entity, name, value):
        self.fields[name] = value

    def guarded(self, entity):
        return False

    def emit(self, kind, roles, **kw):
        self.emitted.append((kind, kw.get("causes")))
        return types.SimpleNamespace(id="e9")


def test_wards_made_whole_answer_their_failure():
    ctx = Stub(ward_failed="e1")
    night.Night().fails(ctx, "s", night.DEFAULT, 0.7)
    assert ctx.emitted[0][0] == "ward.mended" and ctx.fields["ward_failed"] is None
    assert ctx.emitted[0][1] == (Cause("event", "e1"),)


def test_the_night_cites_what_it_took_a_notable_for():
    e = world(notable=1.0, toll=1.0, wards=0.0, mend=0.0, years=1)
    taken = [x for x in of(e, "people.death") if x.payload.get("cause") == "night terrors"]
    assert taken and all(x.causes for x in taken)


def test_a_surge_comes_to_a_region_and_fades():
    e = world(surge=1.0, ebb=1.0, years=1)
    towns = e.store.ids("settlement")
    assert of(e, "night.surge") and all(not e.store.get(s, "level:aberrant") for s in towns)


def test_the_night_replays_the_same():
    a, b = world(years=3), world(years=3)
    assert [x.id for x in a.events] == [x.id for x in b.events]
