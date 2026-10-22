"""Actions (S7 spec §4, #92): each starter action performed alone, at fixed odds, on the kin world."""

import pytest

from renasci.core.calendar import Date
from renasci.core.systems import Ruleset, System
from renasci.kin import START, new_engine, ruleset
from renasci.people import actions as A
from renasci.people.actions import ACTIONS, Action, perform
from renasci.people.races import age_years


def adults(e, sex=None):
    out = []
    for s in e.store.ids("settlement"):
        for p in e.store.get(s, "residents"):
            if age_years(e.calendar, e.store.get(p, "born"), START) >= 20 and (sex is None or e.store.get(p, "sex") == sex):
                out.append(p)
    return out


def act(name, actor, target=None, *, odds=1.0, exposure=0.0, scheme=None, then=(), prepare=None, engine=None):
    """Run `name` (and any `then` steps: (name, actor, target)) a day into a fresh kin world, at fixed
    odds; return the engine and the last outcome."""
    result = {}
    base = ruleset()

    class Harness(System):
        cadence = "on_demand"
        reads = A.READS
        writes = A.WRITES | frozenset({"new:scheme"})
        event_types = A.EVENT_TYPES

        def handle(self, ctx, activation):
            if prepare:
                prepare(ctx)
            for step, who, whom in ((name, actor, target), *then):
                result["outcome"] = perform(ctx, ACTIONS[step], who, whom, scheme=scheme, odds=odds)

    Harness.name = "test.harness"
    params = dict(base.params, exposure_base=exposure)
    e = engine or new_engine()
    rs = Ruleset("t", 1, (Harness(),) + base.systems, params=params, forcers=base.forcers)
    e.rulesets = [(START, rs)]
    e.register_event_types(rs.event_types())  # (swapped in after the engine was built)
    e.run_before(Date(1, 1, 1))  # (the first ruleset switch clears anything queued before the run)
    e.schedule("test.harness", Date(1, 1, 1), "act", entity=actor)
    e.run(until=Date(1, 1, 2))
    return e, result["outcome"]


def test_the_library_is_the_classes():
    assert {"Recruit", "Petition", "CourtFavour", "Court", "Poison", "Assassinate", "Duel", "Shame", "Flee",
            "Confess"} <= set(ACTIONS)
    for a in ACTIONS.values():
        assert isinstance(a.achieves, str) and a.achieves  # exactly one tag


def test_adding_an_action_needs_only_a_new_class():
    class Serenade(Action):
        name, achieves = "Serenade", "charmed:{target}"

    assert "Serenade" in A.library()


def test_poison_kills_in_secret_and_the_world_hears_of_an_illness():
    probe = new_engine()
    poisoner, victim = adults(probe)[0], adults(probe)[5]
    e, outcome = act("Poison", poisoner, victim)
    assert outcome == "success"
    secret = [ev for ev in e.events if ev.type == "people.action" and ev.payload["action"] == "Poison"]
    death = next(ev for ev in e.events if ev.type == "people.death" and ev.roles["deceased"] == (victim,))
    assert secret and secret[0].visibility == "secret"
    assert ("event", secret[0].id) in {(c.kind, c.ref) for c in death.causes}
    assert death.payload["cause"] == "a wasting illness" and not death.roles.get("killer")


def test_a_secret_step_can_be_exposed_and_then_does_nothing():
    probe = new_engine()
    poisoner, victim = adults(probe)[0], adults(probe)[5]
    e, outcome = act("Poison", poisoner, victim, exposure=10.0)
    assert outcome == "exposed" and e.store.status(victim) == "active"


def test_a_duel_kills_openly_and_names_the_killer():
    probe = new_engine()
    a, b = adults(probe, "m")[0], adults(probe, "m")[3]
    e, outcome = act("Duel", a, b)
    death = next(ev for ev in e.events if ev.type == "people.death" and ev.roles["deceased"] == (b,))
    assert outcome == "success" and death.roles["killer"] == (a,)


def test_a_lost_duel_harms_the_challenger():
    probe = new_engine()
    a, b = adults(probe, "m")[0], adults(probe, "m")[3]
    e, outcome = act("Duel", a, b, odds=0.0)
    assert outcome == "failure"
    attempt = next(ev for ev in e.events if ev.type == "people.action" and ev.payload["action"] == "Duel")
    if e.store.status(a) != "active":
        death = next(ev for ev in e.events if ev.type == "people.death" and ev.roles["deceased"] == (a,))
        assert death.roles["killer"] == (b,) and ("event", attempt.id) in {(c.kind, c.ref) for c in death.causes}
    else:
        assert (e.store.get(a, "favour") or 0) < 0  # shamed


def test_favour_is_won_by_petition_then_court_favour():
    probe = new_engine()
    p = adults(probe)[2]
    e, outcome = act("Petition", p)
    assert outcome == "success" and (e.store.get(p, "favour") or 0) >= A.HEARD
    e, outcome = act("Petition", p, then=[("CourtFavour", p, None)])
    assert outcome == "success" and (e.store.get(p, "favour") or 0) >= A.FAVOURED


def test_court_marries_the_unmarried():
    probe = new_engine()
    single = next(p for p in adults(probe, "m") if probe.store.get(p, "spouse") is None)
    e, outcome = act("Court", single)
    assert outcome == "success" and e.store.get(single, "spouse") is not None


def test_shame_costs_favour_and_wounds():
    probe = new_engine()
    a, b = adults(probe)[0], adults(probe)[4]
    e, outcome = act("Petition", a, then=[("Shame", a, b)])  # heard first, then listened to
    assert outcome == "success" and (e.store.get(b, "favour") or 0) < 0
    assert (e.store.get(b, "wound") or {}).get("kind") == "shame"


def test_flee_moves_within_the_region():
    probe = new_engine()
    p = next(x for x in adults(probe) if probe.store.get(x, "spouse") is None and not probe.store.get(x, "house"))
    home = probe.store.get(p, "place")
    e, outcome = act("Flee", p)
    new = e.store.get(p, "place")
    assert outcome == "success" and new != home
    assert e.store.get(new, "region") == e.store.get(home, "region") and p in e.store.get(new, "residents")
    assert e.check_conservation() == []


def test_an_impossible_action_is_not_attempted():
    probe = new_engine()
    p = adults(probe)[0]
    e, outcome = act("Duel", p, p)  # nobody duels themselves
    assert outcome == "impossible" and not [ev for ev in e.events if ev.type == "people.action"]


# ---------------------------------------------------------------- review fixes


def _scheme(owner):
    """A bare scheme record for the harness (schemes proper arrive in #94)."""
    def make(ctx):
        ctx.emit("people.action", {"actor": (owner,)}, purpose="prepare", actor=owner,
                 payload={"action": "prepare", "outcome": "success"},
                 creates={"target": [("scheme", {"owner": owner, "accomplices": [], "state": "active"})]})
    return make


def test_recruit_adds_an_accomplice_to_the_scheme():
    probe = new_engine()
    a, b = adults(probe)[0], adults(probe)[4]
    e, _ = act("Petition", a, prepare=_scheme(a))
    scheme = e.store.ids("scheme")[0]
    e, outcome = act("Recruit", a, b, scheme=scheme, prepare=_scheme(a))
    scheme = e.store.ids("scheme")[0]
    assert outcome == "success" and e.store.get(scheme, "accomplices") == [b]


def test_confess_ends_ones_own_scheme():
    probe = new_engine()
    a = adults(probe)[0]
    e, _ = act("Petition", a, prepare=_scheme(a))
    scheme = e.store.ids("scheme")[0]
    e, outcome = act("Confess", a, scheme=scheme, prepare=_scheme(a))
    assert outcome == "success" and e.store.get(e.store.ids("scheme")[0], "state") == "confessed"


def test_assassination_kills_in_secret():
    probe = new_engine()
    a, b = adults(probe)[0], adults(probe)[5]
    e, outcome = act("Assassinate", a, b)
    death = next(ev for ev in e.events if ev.type == "people.death" and ev.roles["deceased"] == (b,))
    assert outcome == "success" and death.payload["cause"] == "found dead" and not death.roles.get("killer")


def test_success_means_the_tag_holds():
    probe = new_engine()
    p = adults(probe)[2]
    e, outcome = act("Shame", adults(probe)[0], p, then=[("Petition", p, None)])  # shamed, then petitions
    if outcome == "success":
        assert (e.store.get(p, "favour") or 0) >= A.HEARD


def test_the_unheard_cannot_shame_and_the_married_cannot_flee():
    probe = new_engine()
    nobody, other = adults(probe)[0], adults(probe)[4]
    e, outcome = act("Shame", nobody, other)
    assert outcome == "impossible"
    married = next(p for p in adults(probe) if probe.store.get(p, "spouse"))
    e, outcome = act("Flee", married)
    assert outcome == "impossible"


def test_a_name_belongs_to_one_class_only():
    class Echo(A.Poison):  # inherits the name "Poison" but doesn't set its own: not a new action
        duration_days = 999

    assert A.library()["Poison"].duration_days != 999
