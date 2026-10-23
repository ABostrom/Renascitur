"""Grievances follow belief (S6 spec §8, #155): in a world with beliefs, the kin of the dead hold it
against whoever they believe did it, right or wrong."""

import sys
from pathlib import Path

import pytest

from renasci.core.calendar import Span
from renasci.people import actions as A
from renasci.people import beliefs as B
from renasci.people import life

sys.path.insert(0, str(Path(__file__).parent))
from test_beliefs import CAL, SEEN, START, emit_probe_event, engine, scenario  # noqa: E402


def family(ctx):
    """A parent with a living child at home, and two other adults."""
    home = ctx.ids("settlement")[0]
    here = [p for p in ctx.get(home, "residents") if ctx.status(p) == "active" and A._adult(ctx, p)]
    parent = next(p for p in here if any(c in here for c in (ctx.get(p, "children") or [])))
    child = next(c for c in ctx.get(parent, "children") if c in here)
    others = [p for p in here if p not in (parent, child) and p not in (ctx.get(parent, "children") or [])
              and p not in (ctx.get(child, "children") or []) and ctx.get(p, "spouse") not in (parent, child)]
    return home, parent, child, others[0], others[1]


def against(e, holder):
    return sorted(g["against"] for g in (e.store.get(holder, "grievances") or []))


def test_an_open_killing_makes_the_kin_hold_it_against_the_killer_once():
    def go(ctx):
        home, parent, child, killer, _ = family(ctx)
        life.die(ctx, parent, home, "fell in a duel", killer=killer)
        SEEN.update(child=child, killer=killer)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert against(e, SEEN["child"]) == [SEEN["killer"]]  # (once: from the belief, not twice)


def test_a_cover_hides_the_killer_until_the_truth_comes_out():
    def poison(ctx):
        home, parent, child, poisoner, _ = family(ctx)
        SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Poison"], poisoner, parent, odds=1.0)
        SEEN.update(child=child, poisoner=poisoner, parent=parent, home=home)

    def look(ctx):
        SEEN["before"] = sorted(g["against"] for g in (ctx.get(SEEN["child"], "grievances") or []))

    def expose(ctx):
        ev = emit_probe_event(ctx, SEEN["poisoner"])
        B.correct(ctx, SEEN["child"], B.claim("killed", victim=SEEN["parent"], by=SEEN["poisoner"]), ev.id)

    e = engine([(Span(days=1), poison), (Span(days=5), look), (Span(days=10), expose)])
    e.run(until=CAL.add(START, Span(days=20)))
    if SEEN["outcome"] != "success":
        pytest.skip("this seed didn't poison")
    assert SEEN["poisoner"] not in SEEN["before"]  # the cover: nobody to blame
    assert SEEN["poisoner"] in against(e, SEEN["child"])  # the truth: the poisoner


def test_a_frame_aims_the_grievance_at_the_wrong_person():
    def frame(ctx):
        home, parent, child, killer, innocent = family(ctx)
        life.die(ctx, parent, home, "a sudden illness")
        ev = emit_probe_event(ctx, killer)
        B.tell(ctx, killer, child, B.claim("killed", victim=parent, by=innocent), 0.8, conf=0.9, intent="lie",
               cause=ev.id)
        SEEN.update(child=child, innocent=innocent)

    e = engine([(Span(days=1), frame)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert against(e, SEEN["child"]) == [SEEN["innocent"]]


def test_a_stranger_who_believes_it_holds_no_grievance():
    def go(ctx):
        home, parent, child, killer, stranger = family(ctx)
        life.die(ctx, parent, home, "a sudden illness")
        ev = emit_probe_event(ctx, killer)
        B.hold(ctx, stranger, B.claim("killed", victim=parent, by=killer), 0.9, ev.id)
        SEEN.update(stranger=stranger)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert against(e, SEEN["stranger"]) == []


def test_without_beliefs_the_known_killer_rule_stands():
    def go(ctx):
        home, parent, child, killer, _ = family(ctx)
        life.die(ctx, parent, home, "fell in a duel", killer=killer)
        SEEN.update(child=child, killer=killer)

    e = engine([(Span(days=1), go)], sc=scenario(beliefs=False))
    e.run(until=CAL.add(START, Span(days=3)))
    assert against(e, SEEN["child"]) == [SEEN["killer"]]


def test_an_accomplice_holds_no_grievance_against_their_own_co_conspirator():
    def go(ctx):
        home, parent, child, killer, _ = family(ctx)
        ev = ctx.emit("people.action", {"actor": (killer,)}, purpose="probe", actor=killer,
                      payload={"action": "Probe", "outcome": "success"}, visibility="secret")
        life.die(ctx, parent, home, "a wasting illness", causes=(), cover=True, knew=(killer, child))
        B.perceive(ctx, ev.id, None, [killer, child], B.claim("killed", victim=parent, by=killer), secret=True)
        B.correct(ctx, child, B.claim("killed", victim=parent, by=killer), ev.id)  # (exposed later)
        SEEN.update(child=child, killer=killer)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["killer"] not in against(e, SEEN["child"])


def test_a_lie_that_someone_living_was_killed_holds_no_grievance():
    def go(ctx):
        home, parent, child, killer, _ = family(ctx)
        ev = emit_probe_event(ctx, killer)
        B.tell(ctx, killer, child, B.claim("killed", victim=parent, by=killer), 0.9, conf=0.9, intent="lie",
               cause=ev.id)
        SEEN.update(child=child)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert against(e, SEEN["child"]) == []
