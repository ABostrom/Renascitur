"""Schemes (S7 spec §6, #94): ambitions pursued step by step, traceable, exposable, explainable."""

import copy

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.kin import SCENARIO, new_engine

END = Date(1, 60, 359)


def scheming():
    """Kin with traits mapped and plotting made common enough to see in sixty years."""
    sc = copy.deepcopy(SCENARIO)
    sc["params"]["traits"] = {"wits": "stature", "charm": "stature", "temper": "stature"}
    return sc


@pytest.fixture(scope="module")
def world():
    e = new_engine(scenario=scheming())
    e.full_reads = True
    e.run(until=END)
    return e


def of(e, kind):
    return [ev for ev in e.events if ev.type == kind]


def test_ambitions_become_schemes(world):
    begun = of(world, "people.scheme_begun")
    assert len(begun) >= 5
    states = {world.store.get(s, "state") for s in world.store.ids("scheme")}
    assert states <= {"active", "succeeded", "failed", "exposed", "moot", "confessed"}
    assert states - {"active"}  # some have ended
    for s in world.store.ids("scheme"):
        plan = world.store.get(s, "plan")
        assert plan and all({"action", "target"} <= set(step) for step in plan)


def test_every_step_traces_to_its_scheme_and_ambition(world):
    steps = [a for a in world.pending()["activations"]
             if a["system"] == "people.schemes" and any(c[0] == "scheme" for c in a["causes"])]
    assert steps
    by_activation = {}
    for ev in world.events:
        by_activation.setdefault(ev.activation, []).append(ev)
    seen = 0
    for a in steps:
        for ev in by_activation.get(a["activation"], []):
            kinds = {c.kind for c in ev.causes}
            assert {"scheme", "ambition"} <= kinds, (ev.type, ev.causes)
            seen += 1
    assert seen and any(ev.type == "people.action" for a in steps for ev in by_activation.get(a["activation"], []))


def test_ended_schemes_release_their_ambitions(world):
    store = world.store
    for s in store.ids("scheme"):
        if store.get(s, "state") != "active":
            amb = store.get(s, "ambition")
            assert store.get(amb, "scheme") != s


def test_exposure_has_consequences(world):
    store = world.store
    exposed = of(world, "people.scheme_exposed")
    if not exposed:
        pytest.skip("no plot was exposed in this world")
    for ev in exposed:
        scheme = ev.roles["scheme"][0]
        owner = ev.roles["owner"][0]
        amb = store.get(scheme, "ambition")
        assert store.get(amb, "state") in ("thwarted", "died_unfulfilled")
        target = ev.roles.get("target")
        if target:  # (a target already dead when the plot came out holds nothing)
            target = target[0]
            grievances = store.get(target, "grievances") or []
            assert any(g["against"] == owner for g in grievances)


def test_an_attributed_killing_breeds_grievances_in_the_kin(world):
    store = world.store
    for ev in of(world, "people.death"):
        killer = ev.roles.get("killer")
        if not killer:
            continue
        victim = ev.roles["deceased"][0]
        kin = [p for p in [store.get(victim, "spouse"), store.get(victim, "mother"), store.get(victim, "father"),
                           *(store.get(victim, "children") or [])] if p]
        for k in kin:
            assert any(g["against"] == killer[0] and g["event"] == ev.id for g in store.get(k, "grievances") or []) \
                or store.status(k) != "active"


def test_succession_plots_and_vengeance_can_form(world):
    classes = {ev.payload["class"] for ev in of(world, "people.ambition_formed")}
    assert "Seize" in classes or "Vengeance" in classes


def test_those_in_an_active_scheme_are_never_demoted(world):
    store = world.store
    involved_at = {}
    for s in store.ids("scheme"):
        start, end = store.get(s, "started"), store.get(s, "ended")
        for p in [store.get(s, "owner"), store.get(s, "target"), *(store.get(s, "accomplices") or [])]:
            if p:
                involved_at.setdefault(p, []).append((tuple(start), tuple(end) if end else (9, 9999, 0)))
    for ev in of(world, "lod.demote"):
        p = ev.roles["individual"][0]
        for start, end in involved_at.get(p, []):
            assert not (start <= tuple(ev.date.to_json()) < end)


def test_a_protect_ripple_on_a_schemes_target_is_fully_explained(world):
    store = world.store
    deaths = {ev.roles["deceased"][0]: ev for ev in of(world, "people.death")}
    target = next((store.get(s, "target") for s in sorted(store.ids("scheme"))
                   if store.get(s, "target") in deaths and deaths[store.get(s, "target")].date.year >= 5), None)
    if target is None:
        death = next(ev for ev in of(world, "people.death") if 10 <= ev.date.year <= 40 and 20 <= ev.payload["age"] <= 50)
        target = death.roles["deceased"][0]
    when = deaths[target].date
    variant = new_engine(scenario=scheming(), ripples=[
        Ripple("r1", "protect", Date(1, max(1, when.year - 1), 0), target, {"until": [1, 60, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(), ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]


# ---------------------------------------------------------------- review regressions


def test_an_accomplice_who_dies_mid_scheme_is_dropped_and_the_plot_goes_on():
    e = new_engine(scenario=scheming())
    for y in range(1, 60):
        for d in range(0, 360, 30):
            e.run(until=Date(1, y, d))
            live = [s for s in e.store.ids("scheme")
                    if e.store.get(s, "state") == "active" and e.store.get(s, "accomplices")]
            if live:
                s, acc = live[0], e.store.get(live[0], "accomplices")[0]
                e.store.set_status(acc, "dead", Date(1, y, d), "test", "test")
                e.run(until=Date(1, y + 1, d))
                assert acc not in (e.store.get(s, "accomplices") or [])
                return
    pytest.skip("no scheme recruited anyone")


def test_whatever_a_dying_owners_ambitions_read_is_declared():
    from renasci.people.ambitions import LIBRARY
    from renasci.people.life import DIE_READS

    assert "target" in DIE_READS
    for cls in LIBRARY.values():
        assert cls.reads <= DIE_READS | {"drives", "traits", "race", "born", "name", "ended", "ruler", "ids:polity"}, cls.name  # (eligible and text aren't asked at a death)


def test_nobody_holds_a_grievance_against_themselves(world):
    for p in world.store.ids("person"):
        assert all(g["against"] != p for g in world.store.get(p, "grievances") or [])


def test_a_grievance_is_taken_up_once(world):
    seen = {}
    for ev in of(world, "people.ambition_formed"):
        if ev.payload["class"] in ("Vengeance", "Protect"):
            key = (ev.roles["owner"][0], tuple(world.store.get(ev.roles["ambition"][0], "born_of")))
            seen[key] = seen.get(key, 0) + 1
    assert all(n == 1 for n in seen.values()), seen

