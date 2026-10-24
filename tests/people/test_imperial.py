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


def test_a_forced_reign_is_an_abdication_by_a_living_ruler(run):
    deaths = {ev.roles["deceased"][0]: ev.date for ev in run.events if ev.type == "people.death"}
    abdications = [ev for ev in run.events if ev.type == "people.succession" and ev.payload["abdication"]]
    for ev in abdications:
        assert any(c.kind == "pin" for c in ev.causes)
        (pred,) = ev.roles["predecessor"]
        assert pred not in deaths or deaths[pred] > ev.date  # alive when abdicating
    forced = {s["pin"] for s in run.director.strain if s["action"] == "force" and s["pin"].startswith("reign-")}
    caused = {c.ref for ev in run.events if ev.type == "people.succession" and ev.payload["office"] == THRONE
              for c in ev.causes if c.kind == "pin"}
    assert forced <= caused


def quiet_kin(seed):
    """Kin with no marriage markets, so a bachelor stays one until a pin needs him wed."""
    import copy

    from renasci.kin import SCENARIO

    sc = copy.deepcopy(SCENARIO)
    sc["params"]["market_rate"] = 0.0
    sc["params"]["commoner_rate"] = 0.0
    return sc


def test_a_pinned_bachelor_is_married_first():
    from renasci.core.calendar import Date as D
    from renasci.people.races import age_years

    sc = quiet_kin(3)
    probe = new_engine(seed=3, scenario=sc)
    bachelor = next(p for s in probe.store.ids("settlement") for p in probe.store.get(s, "residents")
                    if probe.store.get(p, "sex") == "m" and probe.store.get(p, "spouse") is None
                    and 20 <= age_years(probe.calendar, probe.store.get(p, "born"), D(1, 1, 0)) <= 40)
    e = new_engine(seed=3, scenario=sc, pins=[Pin("heir", "event", window=(D(1, 1, 0), D(1, 1, 10)),
                                                  payload={"type": "people.birth", "roles": {"father": [bachelor]},
                                                           "bind": {"role": "child", "subject": "v:Heir"}})])
    e.run(until=D(1, 2, 0))
    child = e.director.bindings["v:Heir"]
    assert e.director.status["heir"] == "forced" and e.store.get(child, "father") == bachelor
    wedding = next(ev for ev in e.events if ev.type == "people.marriage" and bachelor in ev.roles["spouse"])
    assert ("pin", "heir") in [(c.kind, c.ref) for c in wedding.causes]
    assert e.store.get(e.store.get(child, "mother"), "spouse") == bachelor


def test_a_child_is_not_made_a_father():
    from renasci.core.calendar import Date as D
    from renasci.people.races import age_years

    probe = new_engine(seed=3)
    boy = next(p for s in probe.store.ids("settlement") for p in probe.store.get(s, "residents")
               if probe.store.get(p, "sex") == "m" and age_years(probe.calendar, probe.store.get(p, "born"), D(1, 1, 0)) < 10)
    e = new_engine(seed=3, pins=[Pin("too-soon", "event", window=(D(1, 1, 0), D(1, 1, 10)),
                                     payload={"type": "people.birth", "roles": {"father": [boy]},
                                              "bind": {"role": "child", "subject": "v:Nobody"}})])
    e.run(until=D(1, 2, 0))
    assert e.director.status["too-soon"] == "violated" and "v:Nobody" not in e.director.bindings


def test_a_reigning_ruler_is_guarded_until_the_next_reign_pins_window_opens():
    """(S8 spec §3.4.) The next ruler is born early, but his reign is pinned to a window years later: a
    death of the reigning ruler in between would hand him the throne before his window, and the pin could
    never be met. The holder of a pinned office is guarded until the window opens, then left to fate."""
    first = new_engine(seed=1234).store.get(THRONE, "holder")
    pins = [Pin("born-2", "event", window=(Date(1, 2, 0), Date(1, 5, 359)),
                payload={"type": "people.birth", "roles": {"father": [first]},
                         "bind": {"role": "child", "subject": "v:Ruler-2", "fields": {"sex": "m"}}}),
            Pin("reign-2", "event", window=(Date(1, 20, 0), Date(1, 30, 0)),
                payload={"type": "people.succession", "roles": {"successor": ["v:Ruler-2"]}, "office": THRONE})]
    from renasci.core.ripples import Ripple

    doom = Ripple(id="r", kind="doom", target=first, date=Date(1, 10, 0))  # (after the birth, before the window)
    e = new_engine(seed=1234, pins=pins, ripples=[doom])
    e.run(until=Date(1, 31, 0))
    assert e.director.status["reign-2"] in ("satisfied", "forced"), e.director.strain
    guards = [s for s in e.director.strain if s["action"] == "guard" and s["pin"] == "reign-2"]
    held = [s for s in guards if s["entity"] == first]  # (the reigning ruler: until the window opened)
    assert held and all(s["date"][1] < 20 for s in held)
    assert {s["entity"] for s in guards} <= {first, e.director.bindings["v:Ruler-2"]}  # (and the heir, as before)


def test_inside_a_reign_pins_window_the_holder_is_left_to_fate():
    """(Only an office's next pin guards: a later reign's pin doesn't keep the holder alive through an
    earlier one's open window, so a death there passes the throne on naturally.)"""
    first = new_engine(seed=1234).store.get(THRONE, "holder")
    pins = [Pin("born-2", "event", window=(Date(1, 2, 0), Date(1, 5, 359)),
                payload={"type": "people.birth", "roles": {"father": [first]},
                         "bind": {"role": "child", "subject": "v:Ruler-2", "fields": {"sex": "m"}}}),
            Pin("reign-2", "event", window=(Date(1, 8, 0), Date(1, 30, 0)),
                payload={"type": "people.succession", "roles": {"successor": ["v:Ruler-2"]}, "office": THRONE}),
            Pin("reign-3", "event", window=(Date(1, 60, 0), Date(1, 90, 0)),
                payload={"type": "people.succession", "roles": {"successor": ["v:Ruler-3"]}, "office": THRONE})]
    from renasci.core.ripples import Ripple

    e = new_engine(seed=1234, pins=pins, ripples=[Ripple(id="r", kind="doom", target=first, date=Date(1, 12, 0))])
    e.run(until=Date(1, 13, 0))
    assert e.store.status(first) == "dead"
    assert e.director.status["reign-2"] == "satisfied"  # (naturally: the heir succeeded inside his window)
