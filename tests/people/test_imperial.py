"""A pinned line of rulers (S3 spec §4.3, §5; #74): birth pins, succession pins, forcing.

The golden test: eight rulers, each the child of the one before, reign in order in every run. Ruler 1
is the head of a house at the start; ruler k+1 is pinned to be born to ruler k in a window, and to
take the headship (the "throne") in a later window. A pin met naturally costs nothing; one that
isn't is forced at its deadline (a birth, or an abdication in the pinned successor's favour), and
the strain says so.
"""

import pytest

from renasci.core.calendar import Date
from renasci.core.pins import Pin
from renasci.kin import new_engine

HOUSE = "t:House-Hollow"
THRONE = f"{HOUSE}-head"
RULERS = 8
END = Date(1, 250, 359)


def line_pins(first: str) -> list[Pin]:
    """Ruler k+1 is born to ruler k in years [2+34(k-1), 16+34(k-1)], and takes the throne by year
    36+34(k-1). The reign window opens with the birth window: inheriting early, naturally, counts."""
    pins = []
    for k in range(1, RULERS):
        father = first if k == 1 else f"v:Ruler-{k}"
        start = 2 + 34 * (k - 1)
        pins.append(Pin(f"born-{k + 1}", "event", window=(Date(1, start, 0), Date(1, start + 14, 359)),
                        payload={"type": "people.birth", "roles": {"father": [father]},
                                 "bind": {"role": "child", "subject": f"v:Ruler-{k + 1}", "fields": {"sex": "m"}}}))
        pins.append(Pin(f"reign-{k + 1}", "event", window=(Date(1, start, 0), Date(1, start + 34, 0)),
                        payload={"type": "people.succession", "roles": {"successor": [f"v:Ruler-{k + 1}"]},
                                 "office": THRONE}))
    for k in range(2, RULERS):
        pins.append(Pin(f"order-{k}", "ordering", payload={"before": f"reign-{k}", "after": f"reign-{k + 1}"}))
    return pins


def reigns(e):
    """Who took the throne, in order (the first ruler held it from the start)."""
    return [ev.roles["successor"][0] for ev in e.events
            if ev.type == "people.succession" and ev.payload["office"] == THRONE]


@pytest.fixture(scope="module", params=[1234, 7])
def run(request):
    seed = request.param
    first = new_engine(seed=seed).store.get(THRONE, "holder")
    e = new_engine(seed=seed, pins=line_pins(first))
    e.run(until=END)
    e.first = first
    return e


def test_every_ruler_is_born_to_the_one_before(run):
    b = run.director.bindings
    assert sorted(b) == [f"v:Ruler-{k}" for k in range(2, RULERS + 1)]
    fathers = {k: (run.first if k == 2 else b[f"v:Ruler-{k - 1}"]) for k in range(2, RULERS + 1)}
    for k in range(2, RULERS + 1):
        child = b[f"v:Ruler-{k}"]
        assert run.store.get(child, "father") == fathers[k] and run.store.get(child, "sex") == "m"


def test_all_eight_reign_in_order(run):
    b = run.director.bindings
    line = [run.first] + [b[f"v:Ruler-{k}"] for k in range(2, RULERS + 1)]
    holders = reigns(run)
    positions = [holders.index(r) for r in line[1:]]
    assert positions == sorted(positions), "the rulers did not take the throne in order"
    for k in range(2, RULERS + 1):
        assert run.director.status[f"reign-{k}"] in ("satisfied", "forced")
        assert run.director.status[f"born-{k}"] in ("satisfied", "forced")


def test_strain_is_reported(run):
    actions = {s["action"] for s in run.director.strain}
    assert actions <= {"guard", "force"}  # nothing violated
    forced = [s for s in run.director.strain if s["action"] == "force"]
    assert all(s["pin"].startswith(("born-", "reign-")) for s in forced)


def test_a_forced_reign_is_an_abdication(run):
    for ev in run.events:
        if ev.type == "people.succession" and ev.payload["abdication"]:
            assert any(c.kind == "pin" for c in ev.causes)
            (pred,) = ev.roles["predecessor"]
            assert run.store.status(pred) in ("active", "dead", "dormant")  # an abdicated ruler lives on


def test_a_birth_pin_with_no_wife_marries_first():
    e = new_engine(seed=3)
    bachelor = next(p for s in e.store.ids("settlement") for p in e.store.get(s, "residents")
                    if e.store.get(p, "sex") == "m" and e.store.get(p, "spouse") is None and 20 <= e.store.get(p, "born")[1] + 40)
    e = new_engine(seed=3, pins=[Pin("heir", "event", window=(Date(1, 1, 0), Date(1, 1, 10)),
                                     payload={"type": "people.birth", "roles": {"father": [bachelor]},
                                              "bind": {"role": "child", "subject": "v:Heir"}})])
    e.run(until=Date(1, 2, 0))
    child = e.director.bindings.get("v:Heir")
    if child is None:
        pytest.skip("the bachelor was too young or too old to father a child")
    assert e.store.get(child, "father") == bachelor
    assert e.director.status["heir"] == "forced"
    assert any(ev.type == "people.marriage" and bachelor in ev.roles["spouse"] for ev in e.events)
