"""Belief actions: Slander, Frame, BearWitness (S6 spec §8, #98): deception as a scheming tool."""

import sys
from pathlib import Path

from renasci.core.calendar import Span
from renasci.people import actions as A
from renasci.people import beliefs as B
from renasci.people import life
from renasci.people.planner import plan_for

sys.path.insert(0, str(Path(__file__).parent))
from test_belief_grievances import against, family  # noqa: E402
from test_beliefs import CAL, SEEN, START, emit_probe_event, engine, scenario  # noqa: E402


def setup(ctx, true_killer_known=True):
    """A parent dies at another's hand (the true killer); the schemer knows of it."""
    home, parent, child, killer, schemer = family(ctx)
    life.die(ctx, parent, home, "fell in a duel", killer=killer)
    ev = emit_probe_event(ctx, schemer)
    B.hold(ctx, schemer, B.claim("killed", victim=parent, by=killer), 0.9, ev.id)
    return home, parent, child, killer, schemer


def test_slander_tells_the_town_a_lie_and_shames_its_target():
    def go(ctx):
        home, parent, child, killer, schemer = setup(ctx)
        target = next(p for p in ctx.get(home, "residents") if p not in (parent, child, killer, schemer)
                      and ctx.status(p) == "active" and A._adult(ctx, p))
        before = float(ctx.get(target, "favour") or 0.0)
        SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Slander"], schemer, target, odds=1.0)
        SEEN.update(target=target, before=before, after=float(ctx.get(target, "favour") or 0.0),
                    lie=B.key(B.claim("killed", victim=parent, by=target)))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["outcome"] == "success"  # (this seed isn't exposed: the lie is told)
    lies = [ev for ev in e.events if ev.type == "belief.told" and ev.payload["key"] == SEEN["lie"]]
    assert lies and all(ev.payload["intent"] == "lie" for ev in lies)
    attempt = next(ev for ev in e.events if ev.type == "people.action" and ev.payload["action"] == "Slander")
    assert all(any(c.ref == attempt.id for c in ev.causes) for ev in lies)  # (provenance: the scheme's step)
    assert SEEN["after"] < SEEN["before"]


def test_a_frame_turns_the_kins_grievance_on_the_target():
    def go(ctx):
        home, parent, child, killer, schemer = setup(ctx)
        target = next(p for p in ctx.get(home, "residents") if p not in (parent, child, killer, schemer)
                      and ctx.status(p) == "active" and A._adult(ctx, p))
        SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Frame"], schemer, target, odds=1.0)
        SEEN.update(child=child, target=target)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["outcome"] == "success"
    assert SEEN["target"] in against(e, SEEN["child"])


def test_bearing_witness_corrects_the_town_and_shames_the_killer():
    def go(ctx):
        home, parent, child, killer, schemer = setup(ctx)
        before = float(ctx.get(killer, "favour") or 0.0)
        SEEN["outcome"] = A.perform(ctx, A.ACTIONS["BearWitness"], schemer, killer, odds=1.0)
        SEEN.update(killer=killer, before=before, after=float(ctx.get(killer, "favour") or 0.0))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["outcome"] == "success"
    assert any(ev.type == "belief.corrected" for ev in e.events)
    assert SEEN["after"] < SEEN["before"]


def test_one_can_only_bear_witness_to_what_one_believes():
    def go(ctx):
        home, parent, child, killer, schemer = setup(ctx)
        innocent = next(p for p in ctx.get(home, "residents") if p not in (parent, child, killer, schemer)
                        and ctx.status(p) == "active")
        SEEN["can"] = A.ACTIONS["BearWitness"].possible(ctx, schemer, innocent, None)
        SEEN["can_true"] = A.ACTIONS["BearWitness"].possible(ctx, schemer, killer, None)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN == {"can": False, "can_true": True}


def test_a_schemer_who_isnt_heard_at_court_plans_to_shame_by_deception():
    def go(ctx):
        home, parent, child, killer, schemer = setup(ctx)
        ctx.set(schemer, "favour", 0.0)  # (not heard: Shame is out of reach without courting favour first)
        plan = plan_for(ctx, schemer, [frozenset({f"shamed:{killer}"})])
        SEEN["steps"] = [s["action"] for s in plan.steps] if plan else None

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["steps"] and set(SEEN["steps"]) & {"Slander", "BearWitness", "Frame"}


def test_without_beliefs_there_is_no_deceiving():
    def go(ctx):
        home, parent, child, killer, schemer = family(ctx)
        SEEN["any"] = [n for n in ("Slander", "Frame", "BearWitness")
                       if A.ACTIONS[n].possible(ctx, schemer, killer, None)]

    e = engine([(Span(days=1), go)], sc=scenario(beliefs=False))
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["any"] == []


def test_rivals_scheme_to_ruin_each_other_and_reach_for_lies():
    """In a world with beliefs, a rival or an enemy is someone to ruin; with no killing to pin on them
    honestly, schemes reach for slander and frames (S6 §8: deception as a scheming tool)."""
    import copy
    from collections import Counter

    from renasci import renascita

    sc = copy.deepcopy(renascita.SCENARIO)
    sc["params"]["beliefs"] = True
    e = renascita.new_engine(seed=5, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=25)))
    used = Counter(ev.payload["action"] for ev in e.events if ev.type == "people.action")
    assert used["Slander"] + used["Frame"] > 0, used
    lies = [ev for ev in e.events if ev.type == "belief.told" and ev.payload["intent"] == "lie"]
    by_id = {ev.id: ev for ev in e.events}
    assert lies and all(any(c.kind == "event" and c.ref in by_id and by_id[c.ref].type == "people.action"
                            and by_id[c.ref].payload["action"] in ("Slander", "Frame") for c in ev.causes)
                        for ev in lies)  # (every lie traces to the scheme's step that told it)


def test_without_beliefs_nobody_sets_out_to_ruin_a_rival():
    def go(ctx):
        from renasci.people.ambitions import LIBRARY

        SEEN["eligible"] = [p for p in ctx.ids("person", "active") if LIBRARY["Ruin"].eligible(ctx, p)]

    e = engine([(Span(days=1), go)], sc=scenario(beliefs=False))
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["eligible"] == []
