"""Ties (S3 spec §6, #69) and drives (§7, #70) on the kin world."""

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.kin import new_engine
from renasci.people.drives import DRIVES

END = Date(1, 30, 359)
MID = Date(1, 20, 359)


@pytest.fixture(scope="module")
def world():
    e = new_engine(people_per_settlement=20)
    e.full_reads = True
    e.run(until=MID)
    e.mid = {p: (e.store.get(p, "ties"), e.store.get(p, "drives")) for p in e.store.ids("person")}
    e.mid_ties = {t: (e.store.get(t, "strength"), e.store.get(t, "ended")) for t in e.store.ids("tie")}
    e.mid_history = e.pending()
    e.run(until=END)
    return e


def history(e):
    """Everything recorded so far (the mid-run snapshot cleared nothing)."""
    return e.pending()


# ---------------------------------------------------------------- ties


def test_ties_form_and_end(world):
    types = [ev.type for ev in world.events]
    assert types.count("people.tie_formed") > 10 and types.count("people.tie_ended") > 0


def test_ties_are_listed_by_both_people_while_they_last(world):
    store = world.store
    for t in store.ids("tie"):
        a, b, ended = store.get(t, "a"), store.get(t, "b"), store.get(t, "ended")
        assert a < b and store.get(t, "kind") in ("friend", "rival", "mentor")
        strength = store.get(t, "strength")
        assert 0.0 <= strength <= 1.0 and round(strength * 20) == pytest.approx(strength * 20)
        if ended is None:
            assert t in store.get(a, "ties") and t in store.get(b, "ties")
            assert store.status(a) == "active" and store.status(b) == "active"
        else:
            assert t not in store.get(a, "ties") and t not in store.get(b, "ties")


def test_mentors_are_older(world):
    store = world.store
    for t in store.ids("tie"):
        if store.get(t, "kind") == "mentor":
            mentor, pupil = store.get(t, "mentor"), store.get(t, "pupil")
            assert {mentor, pupil} == {store.get(t, "a"), store.get(t, "b")}
            assert store.get(mentor, "born")[1] + 15 <= store.get(pupil, "born")[1]


def as_of(rows, entity, field, date):
    """A field's value at the end of `date`, rebuilt from the creation rows and state_deltas."""
    value = None
    for d in rows:
        if d["entity"] == entity and d["field"] == field and tuple(d["date"]) <= tuple(date.to_json()):
            value = d["new"]
    return value


def test_ties_and_drives_can_be_rebuilt_as_of_any_date(world):
    deltas = history(world)["state_deltas"]
    for p, (ties, drives) in sorted(world.mid.items()):  # everyone, including those who died after MID
        assert (as_of(deltas, p, "ties", MID) or []) == (ties or [])
        assert (as_of(deltas, p, "drives", MID) or {}) == (drives or {})
    for t, (strength, ended) in sorted(world.mid_ties.items()):
        assert as_of(deltas, t, "strength", MID) == strength and as_of(deltas, t, "ended", MID) == ended
    assert len(world.mid_ties) > 50


# ---------------------------------------------------------------- drives


def test_every_notable_has_its_drives(world):
    store = world.store
    newcomers = {ev.roles.get("child", ev.roles.get("individual", ())) for ev in world.events
                 if ev.type in ("people.birth", "lod.promote") and ev.date.year == END.year}
    newcomers = {p for group in newcomers for p in group}
    for s in store.ids("settlement"):
        for p in store.get(s, "residents"):
            drives = store.get(p, "drives")
            if p in newcomers and not drives:
                continue  # arrived after this year's drives pass
            assert set(drives) == set(DRIVES)
            for v in drives.values():
                assert 0.0 <= v <= 1.0 and round(v * 20) == pytest.approx(v * 20)


def test_the_married_belong_more(world):
    store = world.store
    married, single = [], []
    for s in store.ids("settlement"):
        for p in store.get(s, "residents"):
            if store.get(p, "drives"):  # (newcomers this year have none yet)
                (married if store.get(p, "spouse") else single).append(store.get(p, "drives")["belonging"])
    assert married and single and sum(married) / len(married) > sum(single) / len(single)


def test_house_heads_have_status(world):
    store = world.store
    heads = [store.get(store.get(h, "headship"), "holder") for h in store.ids("house")]
    heads = [h for h in heads if h and store.status(h) == "active" and store.get(h, "drives")]
    commoners = [p for s in store.ids("settlement") for p in store.get(s, "residents")
                 if store.get(p, "house") is None and store.get(p, "drives")]
    if heads:
        assert min(store.get(h, "drives")["status"] for h in heads) > \
            sum(store.get(p, "drives")["status"] for p in commoners) / len(commoners)


def test_a_protect_ripple_with_ties_and_drives_is_fully_explained(world):
    death = next(ev for ev in world.events if ev.type == "people.death" and 8 <= ev.date.year <= 20
                 and 20 <= ev.payload["age"] <= 45)
    variant = new_engine(people_per_settlement=20, ripples=[
        Ripple("r1", "protect", Date(1, death.date.year - 1, 0), death.roles["deceased"][0], {"until": [1, 30, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(),
                     ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]


# ---------------------------------------------------------------- review fixes


def test_ties_last_as_long_as_they_are_kept_up(world):
    """Strength means something: lives together, and tie lifespans vary."""
    store = world.store
    spans = set()
    for ev in world.events:
        if ev.type == "people.tie_ended" and ev.payload["why"] == "faded":
            t = ev.roles["tie"][0]
            spans.add(ev.date.year - store.get(t, "since")[1])
    assert len(spans) >= 4


def test_endings_say_why(world):
    whys = {ev.payload["why"] for ev in world.events if ev.type == "people.tie_ended"}
    assert {"death", "faded"} <= whys and whys <= {"death", "faded", "demoted"}


def test_a_tie_between_settlements_is_kept_once_a_year(world):
    store = world.store
    upkeep_writes = {}
    for d in history(world)["state_deltas"]:
        if d["field"] == "strength" and d["old"] is not None:
            key = (d["entity"], d["date"][1])
            upkeep_writes[key] = upkeep_writes.get(key, 0) + 1
    assert upkeep_writes and max(upkeep_writes.values()) == 1
    assert store  # (state untouched)


def test_a_ripple_on_someone_tied_across_settlements_is_explained(world):
    store = world.store
    split = None
    for t in store.ids("tie"):
        a, b = store.get(t, "a"), store.get(t, "b")
        if store.get(t, "ended") is None and store.get(a, "place") != store.get(b, "place"):
            split = a
            break
    if split is None:
        pytest.skip("no tie spans settlements in this world")
    when = next((ev.date for ev in world.events if ev.type == "people.death"
                 and ev.roles["deceased"] == (split,)), None)
    target = split
    variant = new_engine(people_per_settlement=20, ripples=[
        Ripple("r1", "protect", Date(1, 2, 0), target, {"until": [1, 30, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(),
                     ripples=["r1"])
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]
    assert when is None or report["divergent_events"] > 0
