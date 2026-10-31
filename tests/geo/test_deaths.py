"""Every death meets at one point (vision spec §7): corpses are the sum of a town's dead, whatever killed them."""

import pytest

from renasci import ecology, renascita
from renasci.core.calendar import Span


def scenario(**eco):
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}, **eco}
    return sc


def run(sc, seed=3, years=6):
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


def corpses(e, s):
    return float(e.store.get(s, "level:corpses") or 0.0)


@pytest.fixture(scope="module")
def world():
    return run(scenario(burial={}))


def test_a_towns_corpses_are_all_its_dead(world):
    towns = world.store.ids("settlement")
    assert sum(corpses(world, s) for s in towns) > 0
    for s in towns:
        assert corpses(world, s) == int(world.store.read_column("flow:died", [s])[0]), s


def test_without_the_switch_no_town_keeps_corpses():
    e = run(scenario(), years=2)
    assert all(e.store.get(s, "level:corpses") is None for s in e.store.ids("settlement"))


def test_burial_is_checked():
    with pytest.raises(ValueError, match="burial"):
        ecology.check({**ecology.DEFAULT, "burial": 3}, renascita._scenario(None, crafts=True)["params"]["crafts"])
