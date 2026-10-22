"""Life cycle on the kin test world (S3 spec §4.1-4.2): deaths, births, guards, locality, replay."""

import copy

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.canon import digest
from renasci.core.pins import Pin
from renasci.core.ripples import Ripple
from renasci.kin import RACES, new_engine
from renasci.people.genome import origin_of
from renasci.people.races import Race, age_years, quarterly
from renasci.worlds import get_world

END = Date(1, 30, 359)


def run(until=END, **kw):
    e = new_engine(**kw)
    e.run(until=until)
    return e


@pytest.fixture(scope="module")
def base():
    return run(people_per_settlement=12)


# ---------------------------------------------------------------- races


def test_quarterly_hazards_compound_to_the_annual_one():
    assert (1 - quarterly(0.2)) ** 4 == pytest.approx(0.8)


@pytest.mark.parametrize("change, message", [
    (lambda r: r["mortality"]["f"].pop(), "20"),
    (lambda r: r["fertility"].__setitem__(3, 1.5), "probability"),
    (lambda r: r.__setitem__("fertile", [45, 16]), "fertile"),
    (lambda r: r["names"].__setitem__("m", []), "names"),
    (lambda r: r.__setitem__("spacing_days", -1), "spacing"),
])
def test_bad_races_are_refused(change, message):
    data = copy.deepcopy(RACES[0])
    change(data)
    with pytest.raises(ValueError, match=message):
        Race.from_json(data)


# ---------------------------------------------------------------- the S1 guarantees on the kin world


def test_kin_runs_deterministically(base):
    again = run(people_per_settlement=12)
    assert digest(again.pending()["events"]) == digest(base.pending()["events"])
    assert again.state_hash() == base.state_hash()


def test_replay_from_a_checkpoint_matches_the_continuous_run(base):
    at = Date(1, 11, 45)
    e = new_engine(people_per_settlement=12)
    e.run_before(at)
    prefix = e.pending()["events"]
    e.clear_pending()
    cp = e.checkpoint(at=at, segments=0)
    restored = get_world("kin").restore(cp, 1234, people_per_settlement=12)
    restored.run(until=END)
    assert digest(prefix + restored.pending()["events"]) == digest(base.pending()["events"])
    assert restored.state_hash() == base.state_hash()


def test_life_goes_on(base):
    types = {ev.type for ev in base.events}
    assert {"people.birth", "people.death"} <= types


# ---------------------------------------------------------------- invariants


def test_the_dead_leave_their_settlement_and_spouse(base):
    store = base.store
    residents = {p for s in store.ids("settlement") for p in store.get(s, "residents")}
    for p in store.ids("person"):
        if store.status(p) == "dead":
            assert p not in residents
        else:
            assert p in residents and p in store.get(store.get(p, "place"), "residents")
    for p in residents:
        spouse = store.get(p, "spouse")
        assert spouse is None or (store.status(spouse) == "active" and store.get(spouse, "spouse") == p)


def test_births_follow_the_rules(base):
    store, cal = base.store, base.calendar
    race = {r["id"]: Race.from_json(r) for r in RACES}
    last: dict[str, tuple] = {}
    births = [ev for ev in base.events if ev.type == "people.birth"]
    assert births
    for ev in births:
        mother, (father,) = ev.roles["mother"][0], ev.roles["father"]
        r = race[store.get(mother, "race")]
        assert r.fertile[0] <= age_years(cal, store.get(mother, "born"), ev.date) <= r.fertile[1]
        if mother in last:
            gap = (ev.date.year - last[mother].year) * cal.days_per_year + ev.date.day - last[mother].day
            assert gap >= r.spacing_days
        last[mother] = ev.date
        for child in ev.roles["child"]:
            assert child in store.get(mother, "children") and child in store.get(father, "children")
            assert store.get(child, "mother") == mother and store.get(child, "father") == father
            assert store.get(child, "born") == ev.date.to_json()
            for locus, (from_m, from_f) in store.get(child, "genome").items():
                assert from_m in store.get(mother, "genome")[locus] or origin_of(from_m) == ev.id
                assert from_f in store.get(father, "genome")[locus] or origin_of(from_f) == ev.id


def test_mortality_follows_the_life_table():
    flat = copy.deepcopy(RACES)
    for r in flat:
        r["mortality"] = {"f": [0.1] * 20, "m": [0.1] * 20}
        r["fertility"] = [0.0] * 20
    e = run(until=Date(1, 5, 359), people_per_settlement=200, races=flat)
    alive = sum(1 for p in e.store.ids("person") if e.store.status(p) == "active")
    started = 200 * len(e.store.ids("settlement"))
    assert alive / started == pytest.approx(0.9 ** 5, abs=0.03)


# ---------------------------------------------------------------- pins and ripples


def test_a_guarded_person_survives_as_a_near_miss():
    doomed = copy.deepcopy(RACES)
    for r in doomed:
        r["mortality"] = {"f": [1.0] * 20, "m": [1.0] * 20}
    first = new_engine(people_per_settlement=4).store.ids("person")[0]
    e = run(until=Date(1, 2, 359), people_per_settlement=4, races=doomed,
            pins=[Pin("p", "existence", subject=first, window=(Date(1, 1, 0), Date(1, 3, 0)))])
    assert e.store.status(first) == "active"
    assert any(ev.type == "people.near_miss" and ev.roles["survivor"] == (first,) for ev in e.events)
    assert {s["action"] for s in e.director.strain} == {"guard"}


def test_a_protect_ripple_has_no_unexplained_divergence():
    base = new_engine(people_per_settlement=12)
    base.full_reads = True
    base.run(until=END)
    deaths = [ev for ev in base.events if ev.type == "people.death" and 5 <= ev.date.year <= 15]
    target = deaths[0].roles["deceased"][0]
    variant = new_engine(people_per_settlement=12,
                         ripples=[Ripple("r1", "protect", Date(1, deaths[0].date.year - 1, 0), target,
                                         {"until": [1, 30, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(base.pending(), variant.pending(), base.store.to_json(), variant.store.to_json(), ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]


def test_mutations_record_the_birth_they_happened_in():
    from renasci.kin import CATALOGUE

    mutant = copy.deepcopy(CATALOGUE)
    for locus in mutant["loci"]:
        locus["mutation"] = 1.0
    e = run(until=Date(1, 10, 359), people_per_settlement=12, catalogue=mutant)
    births = [ev for ev in e.events if ev.type == "people.birth"]
    assert births
    for ev in births:
        child = ev.roles["child"][0]
        assert all(origin_of(c) == ev.id for pair in e.store.get(child, "genome").values() for c in pair)
        assert ev.payload["mutations"] == 2 * len(mutant["loci"])


# ---------------------------------------------------------------- review fixes


def test_a_protect_ripple_stays_in_the_target_region():
    """Births and deaths are settlement-scoped; marriages are regional (a wife moves), so a ripple's
    reach is its region."""
    from renasci.kin import REGION_OF

    base = new_engine(people_per_settlement=12)
    base.run(until=END)
    death = next(ev for ev in base.events if ev.type == "people.death" and 5 <= ev.date.year <= 15)
    target, home = death.roles["deceased"][0], death.place
    variant = new_engine(people_per_settlement=12, ripples=[
        Ripple("r1", "protect", Date(1, death.date.year - 1, 0), target, {"until": [1, 30, 359]})])
    variant.run(until=END)
    where = {ev["id"]: ev["scope"] for ev in base.pending()["events"] + variant.pending()["events"]}
    report = analyse(base.pending(), variant.pending(), base.store.to_json(), variant.store.to_json(), ripples=["r1"])
    divergent = report["divergent"]["only_baseline"] + report["divergent"]["only_variant"] + report["divergent"]["changed"]
    touched = {where[i] for i in divergent} - {None}  # None: the ripple's own events
    assert divergent and {REGION_OF.get(s, s) for s in touched} <= {REGION_OF[home]}


def test_mutated_copies_are_created_with_their_origin():
    from renasci.kin import CATALOGUE

    mutant = copy.deepcopy(CATALOGUE)
    for locus in mutant["loci"]:
        locus["mutation"] = 1.0
    e = run(until=Date(1, 10, 359), people_per_settlement=12, catalogue=mutant)
    created = {row["id"]: row for row in e.pending()["entities"]}
    births = [ev for ev in e.events if ev.type == "people.birth"]
    for ev in births:
        child = ev.roles["child"][0]
        assert "_birth" not in str(created[child])
    assert not [d for d in e.pending()["state_deltas"] if d["field"] == "genome" and d["old"] is not None]  # no rewrite


def test_no_one_starts_married_under_age():
    e = new_engine(people_per_settlement=40)
    race = {r["id"]: Race.from_json(r) for r in RACES}
    for p in e.store.ids("person"):
        if e.store.get(p, "spouse"):
            assert age_years(e.calendar, e.store.get(p, "born"), Date(1, 1, 0)) >= race[e.store.get(p, "race")].marriage[0]


def test_twins_get_different_names():
    twinny = copy.deepcopy(RACES)
    for r in twinny:
        r["twins"] = 1.0
    e = run(until=Date(1, 12, 359), people_per_settlement=12, races=twinny)
    pairs = [ev.roles["child"] for ev in e.events if ev.type == "people.birth"]
    assert pairs and all(e.store.get(a, "name") != e.store.get(b, "name") for a, b in pairs)


def test_a_cast_person_pinned_for_a_later_window_is_guarded_until_then():
    doomed = copy.deepcopy(RACES)
    for r in doomed:
        r["mortality"] = {"f": [1.0] * 20, "m": [1.0] * 20}
    first = new_engine(people_per_settlement=4).store.ids("person")[0]
    e = run(until=Date(1, 3, 359), people_per_settlement=4, races=doomed,
            pins=[Pin("p", "existence", subject=first, window=(Date(1, 3, 0), Date(1, 4, 0)))])
    assert e.store.status(first) == "active"  # kept alive from the start, not only inside the window
    assert any(ev.type == "people.near_miss" and ev.date.year == 1 for ev in e.events)
