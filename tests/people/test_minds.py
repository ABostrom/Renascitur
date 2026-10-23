"""Minds (S7 spec §7, #95): wounds, needs and wants, written on change and visible as of any date."""

import copy

import pytest

from renasci.core.calendar import Date
from renasci.kin import SCENARIO, new_engine
from renasci.people.ambitions import LIBRARY
from renasci.people.minds import NEEDS, WOUNDS

MID = Date(1, 30, 0)
END = Date(1, 50, 0)  # (a yearly day: minds has just run, after ambitions and schemes)


def scheming():
    sc = copy.deepcopy(SCENARIO)
    sc["params"]["traits"] = {"wits": "stature", "charm": "stature", "temper": "stature"}
    return sc


@pytest.fixture(scope="module")
def world():
    e = new_engine(scenario=scheming())
    e.run(until=MID)
    e.mid = {p: {f: copy.deepcopy(e.store.get(p, f)) for f in ("wound", "need", "wants")} for p in e.store.ids("person")}
    e.run(until=END)
    e.history = e.pending()
    return e


def of(e, kind):
    return [ev for ev in e.events if ev.type == kind]


def as_of(rows, entity, field, date):
    value = None
    for d in rows:
        if d["entity"] == entity and d["field"] == field and tuple(d["date"]) <= tuple(date.to_json()):
            value = d["new"]
    return value


def test_wounds_are_of_the_known_kinds_and_several_appear(world):
    kinds = {d["new"]["kind"] for d in world.history["state_deltas"] if d["field"] == "wound" and d["new"]}
    assert kinds <= set(WOUNDS)
    assert {"grief", "shame"} <= kinds


def test_a_near_miss_leaves_terror():
    """Only the guarded survive a death draw (a protect ripple): they come away terrified."""
    from renasci.core.ripples import Ripple

    probe = new_engine(scenario=scheming())
    oldest = min((p for s in probe.store.ids("settlement") for p in probe.store.get(s, "residents")),
                 key=lambda p: (tuple(probe.store.get(p, "born")), p))
    e = new_engine(scenario=scheming(), ripples=[Ripple("r1", "protect", Date(1, 1, 0), oldest,
                                                        {"until": [1, 30, 359]})])
    e.run(until=Date(1, 30, 359))
    misses = of(e, "people.near_miss")
    assert misses
    deltas = e.pending()["state_deltas"]
    for ev in misses:
        w = as_of(deltas, ev.roles["survivor"][0], "wound", ev.date)
        assert w and w["kind"] == "terror" and w["event"] == ev.id


def test_a_violent_death_leaves_grief_in_the_kin(world):
    """Every close kin alive at a death by a known hand carries grief for it (or a fresher wound that day)."""
    deltas = world.history["state_deltas"]
    store, seen = world.store, 0
    for ev in of(world, "people.death"):
        if not ev.roles.get("killer"):
            continue
        victim, killer = ev.roles["deceased"][0], ev.roles["killer"][0]
        kin = {store.get(victim, "mother"), store.get(victim, "father"), *(store.get(victim, "children") or [])}
        for k in sorted(p for p in kin if p and p != killer):
            if store.get(k, "born") > ev.date.to_json() or not _alive_at(world, k, ev.date):
                continue
            w = as_of(deltas, k, "wound", ev.date)
            assert w and (w["event"] == ev.id or w["since"] == ev.date.to_json()), (k, ev.id, w)
            assert w["event"] != ev.id or (w["kind"] == "grief" and as_of(deltas, k, "need", ev.date) == NEEDS["grief"])
            seen += 1
    assert seen


def _alive_at(world, person, date):
    """Active (not dead, not faded into the masses) at the end of `date`."""
    return as_of(world.history["state_deltas"], person, "status", date) in (None, "active")


def test_an_exposed_friend_betrays(monkeypatch):
    """Force every plot against someone into exposure: a friend who plotted turns enemy and betrays."""
    from renasci.people import schemes

    real = schemes.A.perform

    def exposed(ctx, action, actor, target, scheme=None, odds=None):
        if target and action.name not in ("Recruit", "Confess"):
            return "exposed"
        return real(ctx, action, actor, target, scheme, odds)

    monkeypatch.setattr(schemes.A, "perform", exposed)
    sc = scheming()
    sc["params"].update({"tie_rate": 0.6, "scheme_rate": 1.0})
    e = new_engine(scenario=sc)
    e.run(until=Date(1, 30, 0))
    betrayed = [ev for ev in of(e, "people.tie_ended") if ev.payload["why"] == "betrayed"]
    assert betrayed
    deltas = e.pending()["state_deltas"]
    exposures = {ev.id: ev for ev in of(e, "people.scheme_exposed")}
    for ev in betrayed:
        x = next(x for x in exposures.values() if x.date == ev.date and set(x.roles["owner"] + x.roles["target"])
                 == set(ev.roles["a"] + ev.roles["b"]))
        victim = x.roles["target"][0]
        w = as_of(deltas, victim, "wound", ev.date)
        assert w["kind"] == "betrayal" and w["event"] == x.id
        assert as_of(deltas, victim, "need", ev.date) == NEEDS["betrayal"]


def test_needs_are_world_data():
    sc = scheming()
    sc["params"]["needs"] = {"grief": "to light a lamp for the dead"}
    e = new_engine(scenario=sc)
    e.run(until=Date(1, 30, 0))
    needs = {d["new"] for d in e.pending()["state_deltas"] if d["field"] == "need" and d["new"]}
    assert "to light a lamp for the dead" in needs and NEEDS["grief"] not in needs


def test_wounds_heal(world):
    years = 10
    for p in world.store.ids("person"):
        w = world.store.get(p, "wound")
        if w and world.store.status(p) == "active":
            assert w["since"][1] + years > END.year, (p, w)


def test_need_follows_the_wound_and_wants_are_the_ambitions(world):
    store = world.store
    for s in store.ids("settlement"):
        for p in store.get(s, "residents"):
            w = store.get(p, "wound")
            assert store.get(p, "need") == (NEEDS[w["kind"]] if w else None)
            texts = [LIBRARY[store.get(a, "class")].text(_Reader(store), p, store.get(a, "target"))
                     for a in store.get(p, "ambitions") or []]
            assert (store.get(p, "wants") or []) == texts


class _Reader:
    """Enough of a ctx for an ambition's `text`."""

    def __init__(self, store):
        self.store = store

    def get(self, entity, field):
        return self.store.get(entity, field)


def test_minds_are_written_only_on_change(world):
    for d in world.history["state_deltas"]:
        if d["field"] in ("wound", "need", "wants"):
            assert d["new"] != d.get("old"), d


def test_minds_can_be_rebuilt_as_of_any_date(world):
    deltas = world.history["state_deltas"]
    nonempty = 0
    for p, fields in sorted(world.mid.items()):
        for f, v in fields.items():
            assert as_of(deltas, p, f, MID) == v, (p, f)
            nonempty += bool(v)
    assert nonempty > 20
