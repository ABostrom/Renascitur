import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "helpers"))
sys.path.insert(0, str(Path(__file__).parent))

from mini_world import CAL, DEATH, START  # noqa: E402
from test_pins import COMET, Reaper  # noqa: E402

from renasci.core.calendar import Date  # noqa: E402
from renasci.core.engine import Engine  # noqa: E402
from renasci.core.events import Cause, EventType  # noqa: E402
from renasci.core.ripples import Disguise, Ripple  # noqa: E402
from renasci.core.systems import Ruleset  # noqa: E402

FALL = EventType("mini.fall", 1, roles={"victim": (1, 1)}, payload={})


class Fall(Disguise):
    """Doom, disguised: a fall from a horse."""

    name = "mini.fall"
    handles = "doom"
    reads, writes = frozenset({"status"}), frozenset({"status"})
    event_types = (FALL,)

    def apply(self, ctx, ripple):
        if ctx.status(ripple.target) != "active":
            return False
        ctx.emit("mini.fall", {"victim": (ripple.target,)}, purpose="fall", actor=ripple.target)
        ctx.set_status(ripple.target, "dead")
        return True


class Comet(Disguise):
    name = "mini.comet_sighting"
    handles = "inject"
    event_types = (COMET,)

    def apply(self, ctx, ripple):
        ctx.emit("mini.comet", {}, purpose="sighting", actor=ripple.target)
        return True


def engine(ripples=(), disguises=(Fall(), Comet()), systems=(Reaper(),)):
    e = Engine(CAL, seed=1, rulesets=[(START, Ruleset("r", 1, tuple(systems), disguises=tuple(disguises)))])
    e.cast("person", "t:Ada", {})
    e.cast("place", "t:sky", {})
    e.apply_ripples(ripples)
    return e


# ---------------------------------------------------------------- the three kinds


def test_protect_turns_a_death_into_a_near_miss_caused_by_the_ripple():
    e = engine([Ripple("r1", "protect", Date(1, 2, 0), "t:Ada", {"until": [1, 5, 0]})])
    e.run(until=Date(1, 6, 0))
    assert e.store.status("t:Ada") == "active"
    near = next(ev for ev in e.events if ev.type == "mini.near_miss")
    assert Cause("ripple", "r1") in near.causes
    assert ("event", near.id) in e.causes.descendants(("ripple", "r1"))


def test_protect_expires():
    e = engine([Ripple("r1", "protect", Date(1, 1, 0), "t:Ada", {"until": [1, 2, 0]})])
    e.run(until=Date(1, 6, 0))
    assert e.store.status("t:Ada") == "dead"


def test_doom_applies_through_its_disguise_and_leaves_a_secret_ripple_event():
    e = engine([Ripple("r2", "doom", Date(1, 2, 100), "t:Ada")], systems=())
    e.run(until=Date(1, 3, 0))
    assert e.store.status("t:Ada") == "dead"
    secret = next(ev for ev in e.events if ev.type == "ripple.doom")
    fall = next(ev for ev in e.events if ev.type == "mini.fall")
    assert secret.visibility == "secret" and secret.source.kind == "ripple"
    assert fall.visibility == "public" and Cause("event", secret.id) in fall.causes
    assert [ev.date for ev in (secret, fall)] == [Date(1, 2, 100)] * 2


def test_inject_adds_an_event_through_its_disguise():
    e = engine([Ripple("r3", "inject", Date(1, 2, 0), "t:sky")], systems=())
    e.run(until=Date(1, 3, 0))
    comet = next(ev for ev in e.events if ev.type == "mini.comet")
    assert ("event", comet.id) in e.causes.descendants(("ripple", "r3"))


# ---------------------------------------------------------------- validation


def test_ripples_need_a_disguise_a_known_kind_and_a_date_in_the_run():
    with pytest.raises(ValueError):
        engine([Ripple("r", "doom", Date(1, 2, 0), "t:Ada")], disguises=())
    with pytest.raises(ValueError):
        Ripple("r", "smite", Date(1, 2, 0), "t:Ada")
    with pytest.raises(ValueError):
        engine([Ripple("r", "protect", Date(1, 2, 0), "t:Ada", {"until": [1, 1, 0]})])  # ends before it starts
    with pytest.raises(ValueError):
        engine([Ripple("r", "favour", Date(1, 2, 0), "t:Ada")])  # S1 supports protect, doom, inject


def test_a_failed_disguise_is_recorded_not_fatal():
    e = engine([Ripple("r2", "doom", Date(1, 2, 0), "t:Ada"), Ripple("r4", "doom", Date(1, 3, 0), "t:Ada")],
               systems=())
    e.run(until=Date(1, 4, 0))
    assert [s["ripple"] for s in e.ripple_log if not s["applied"]] == ["r4"]


# ---------------------------------------------------------------- replay with a new ripple


def test_replay_from_a_checkpoint_with_a_new_ripple():
    base = engine()
    base.run_before(Date(1, 2, 0))
    base.clear_pending()
    cp = base.checkpoint(at=Date(1, 2, 0), segments=0)
    rulesets = base.rulesets
    new = [Ripple("r1", "protect", Date(1, 2, 0), "t:Ada", {"until": [1, 5, 0]})]
    r = Engine.restore(cp, CAL, rulesets, seed=1, ripples=new)
    r.run(until=Date(1, 6, 0))
    assert r.store.status("t:Ada") == "active"
    plain = Engine.restore(cp, CAL, rulesets, seed=1)
    plain.run(until=Date(1, 6, 0))
    assert plain.store.status("t:Ada") == "dead"


def test_a_ripple_before_the_checkpoint_cannot_be_added_on_replay():
    base = engine()
    base.run_before(Date(1, 2, 0))
    base.clear_pending()
    cp = base.checkpoint(at=Date(1, 2, 0), segments=0)
    early = [Ripple("r1", "protect", Date(1, 1, 100), "t:Ada", {"until": [1, 5, 0]})]
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, base.rulesets, seed=1, ripples=early)


def test_ripples_before_the_checkpoint_must_match_the_original():
    r = [Ripple("r0", "inject", Date(1, 1, 50), "t:sky")]
    base = engine(r, systems=())
    base.run_before(Date(1, 2, 0))
    base.clear_pending()
    cp = base.checkpoint(at=Date(1, 2, 0), segments=0)
    Engine.restore(cp, CAL, base.rulesets, seed=1, ripples=r)
    with pytest.raises(ValueError):
        Engine.restore(cp, CAL, base.rulesets, seed=1, ripples=())


def test_runs_with_the_same_ripples_are_identical():
    def run():
        e = engine([Ripple("r2", "doom", Date(1, 2, 100), "t:Ada")])
        e.run(until=Date(1, 4, 0))
        return [ev.to_json() for ev in e.events]

    assert run() == run()
