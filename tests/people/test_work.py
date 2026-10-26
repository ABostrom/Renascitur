"""Jobs, skills and wealth (S9 spec §2, #123): in a world with a `crafts` catalogue, each adult notable takes
a job, works it into skill, earns by it, and the masses hold job shares that drift toward the town's demand."""

import copy

import pytest

from renasci import kin, renascita
from renasci.core.calendar import Date
from renasci.people.population import masses

JOBS = {
    "farmer": {"name": "farmer", "demand": 0.5, "income": 1.0},
    "smith": {"name": "smith", "demand": 0.1, "income": 3.0, "makes": ["blade", "tool"]},
    "merchant": {"name": "merchant", "demand": 0.1, "income": 4.0},
    "soldier": {"name": "soldier", "demand": 0.2, "income": 2.0},
    "steward": {"name": "steward", "demand": 0.1, "income": 3.0},
}
CRAFTS = {"jobs": JOBS}


def world(crafts=CRAFTS, years=12, seed=3):
    sc = copy.deepcopy(kin.SCENARIO)
    if crafts is not None:
        sc["params"]["crafts"] = crafts
    e = kin.new_engine(seed=seed, scenario=sc)
    e.run(until=Date(1, years, 359))
    return e


@pytest.fixture(scope="module")
def worked():
    return world()


def adults(e, when=Date(1, 12, 359)):
    from renasci.people.races import age_years

    return [p for s in e.store.ids("settlement") for p in e.store.get(s, "residents")
            if age_years(e.calendar, e.store.get(p, "born"), when) >= 20]


def test_every_grown_notable_has_a_job_from_the_catalogue(worked):
    grown = adults(worked)
    jobbed = [p for p in grown if worked.store.get(p, "job") in JOBS]
    assert grown and len(jobbed) >= 0.95 * len(grown)  # (the rest came this year: promoted, or arrived, after its step)
    assert all(worked.store.get(p, "job") in (None, *JOBS) for p in grown)
    taken = [x for x in worked.events if x.type == "people.job"]
    assert taken and all(x.payload["job"] in JOBS for x in taken)


def test_the_town_gets_the_trades_it_needs(worked):
    held = [worked.store.get(p, "job") for p in adults(worked)]
    assert held.count("farmer") > held.count("smith")  # (demand 0.5 against 0.1)


def test_work_grows_skill_and_wealth(worked):
    first = {x.roles["worker"][0]: x.date for x in worked.events if x.type == "people.job"}
    veterans = [p for p in adults(worked) if p in first and first[p].year <= 2]
    assert veterans
    for p in veterans:
        job = worked.store.get(p, "job")
        assert worked.store.get(p, "skills")[job] > 0
        assert worked.store.get(p, "wealth") > 0


def test_the_masses_hold_job_shares_summing_to_their_number(worked):
    for s in worked.store.ids("settlement"):
        cols = worked.store.read_column  # (columns: one per job)
        held = {j: int(cols(f"job:{j}", [s])[0]) for j in JOBS}
        total = int(sum(held.values()))
        n = sum(int(worked.store.read_column(c, [s])[0]) for c in worked.store._columns if c.startswith("pop:"))
        assert abs(total - n) <= max(5, 0.1 * n)  # (exact at each yearly step; the masses move by season)
        if n >= 100:
            assert held["farmer"] > held["smith"]


def test_the_same_seed_works_the_same():
    a, b = world(years=4), world(years=4)
    sig = lambda e: [(x.date, x.roles["worker"], x.payload["job"]) for x in e.events if x.type == "people.job"]
    assert sig(a) == sig(b) and sig(a)


def test_a_world_without_crafts_has_no_work():
    e = world(crafts=None, years=3)
    assert not [x for x in e.events if x.type in ("people.job", "people.work")]
    assert "people.work" not in {s.name for s in e.rulesets[0][1].systems}
    assert not any(c.startswith("job:") for c in e.store._columns)


@pytest.mark.parametrize("bad", [{"jobs": {"x": {"demand": -1}}}, {"jobs": {"x": 5}}, {"jobs": {}},
                                 {"jobs": {"x": {"demand": float("nan")}}}, {"jobs": {"x": {"demand": True}}},
                                 {"jobs": {"x": {"demand": 1, "income": -2}}}, {"nope": 1}])
def test_a_catalogue_must_name_its_jobs_properly(bad):
    from renasci.people.life import world_params

    with pytest.raises(ValueError):
        world_params(kin.SCENARIO["races"], kin.SCENARIO["catalogue"], crafts=bad)


def test_shares_sum_exactly_and_follow_demand():
    from renasci.people.work import shares

    assert shares(0, {"a": 1.0, "b": 2.0}) == {"a": 0, "b": 0}
    s = shares(10, {"a": 0.5, "b": 0.3, "c": 0.2})
    assert sum(s.values()) == 10 and s == {"a": 5, "b": 3, "c": 2}
    odd = shares(7, {"a": 1.3, "b": 2.2, "c": 0.5})
    assert sum(odd.values()) == 7 and odd["b"] >= odd["a"] >= odd["c"]


def test_renascita_has_a_draft_catalogue_when_asked():
    sc = renascita._scenario(None, crafts=True)
    assert sc["params"]["crafts"]["jobs"] and sc["params"]["crafts"].get("draft") is True
    assert "crafts" not in renascita._scenario(None)["params"]
