"""Extension points beyond the first pools (#162): goals, what an action means, capabilities, reactions."""

import sys
import textwrap
import types

import pytest

from renasci import renascita
from renasci.core.calendar import Span
from renasci.core.pools import base, load
from renasci.people import planner

EXT = """
    from renasci.core.events import EventType
    from renasci.core.pools import Reaction
    from renasci.people.planner import Goal

    MOURNED = EventType("beat.mourned", 1, roles={"who": (1, 1)}, payload={"status": "str"}, dead_roles=("who",))
    WEPT = EventType("beat.wept", 1, roles={"who": (1, 1)}, payload={}, dead_roles=("who",))


    def mourn(ctx, event):
        who = event.roles["deceased"][0]
        ctx.emit("beat.mourned", {"who": (who,)}, purpose="mourn", actor=who, payload={"status": ctx.status(who)})


    def weep(ctx, event):
        who = event.roles["who"][0]
        ctx.emit("beat.wept", {"who": (who,)}, purpose="weep", actor=who)


    def extend(pools):
        pools.event_types.add(MOURNED)
        pools.event_types.add(WEPT)
        pools.reactions.add(Reaction("mourn", "people.death", mourn, frozenset({"status"}), emits=("beat.mourned",)))
        pools.reactions.add(Reaction("weep", "beat.mourned", weep, emits=("beat.wept",)))
        pools.goals.add(Goal("rich", lambda ctx, owner, ref, scheme: True))
"""


@pytest.fixture
def ext(tmp_path, monkeypatch):
    (tmp_path / "ext_points.py").write_text(textwrap.dedent(EXT), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    yield "ext_points"
    sys.modules.pop("ext_points", None)


def years(e, n):
    e.run(until=renascita.CAL.add(renascita.START, Span(years=n)))
    return e


def of(e, t):
    return [x for x in e.events if x.type == t]


def test_every_goal_lives_in_the_pool():
    assert {"tie", "dead", "married", "hostile", "accomplice"} <= set(base().goals)


def test_an_unknown_goal_is_never_true_yet():
    assert planner.holds(types.SimpleNamespace(pools=base()), "p", "nobody-knows:x") is False


def test_an_extension_adds_a_goal(ext):
    ctx = types.SimpleNamespace(pools=load([ext]))
    assert planner.holds(ctx, "p", "rich:x") is True


def test_an_action_means_what_it_achieves_unless_it_says_otherwise():
    from renasci.people.actions import ACTIONS, Action

    assert ACTIONS["Poison"].harms and ACTIONS["Poison"].grave and ACTIONS["Poison"].kills
    assert not ACTIONS["Petition"].harms and not ACTIONS["Petition"].grave

    class Curse(Action):
        achieves, harms, grave = "cursed:{target}", True, True

    assert Curse().harms and Curse().grave and not Curse().kills


def test_capabilities_replace_names():
    from renasci.people.ambitions import LIBRARY

    assert [n for n, a in LIBRARY.items() if a.claims_seat] == ["Seize"]
    assert [n for n, a in LIBRARY.items() if a.casus_belli] == ["Expand"]


def test_a_reaction_answers_its_event_and_says_it_was_authored(ext):
    e = renascita.new_engine(seed=3)
    e.extend([ext])
    years(e, 3)
    deaths = {x.id for x in of(e, "people.death")}
    mourned = of(e, "beat.mourned")
    assert mourned and all(x.source.kind == "reaction" and x.source.ref == "mourn" for x in mourned)
    assert all(deaths & {c.ref for c in x.causes} for x in mourned)


def test_a_reaction_can_answer_a_reaction(ext):
    e = renascita.new_engine(seed=3)
    e.extend([ext])
    years(e, 2)
    mourned = {x.id for x in of(e, "beat.mourned")}
    wept = of(e, "beat.wept")
    assert wept and all(mourned & {c.ref for c in x.causes} for x in wept)
    deaths = {x.id for x in of(e, "people.death")}
    assert not any(deaths & {c.ref for c in x.causes} for x in wept)  # (one step at a time)
    assert all(x.source.ref == "weep" for x in wept)


def test_a_reaction_sees_the_world_after_its_event(ext):
    e = renascita.new_engine(seed=3)
    e.extend([ext])
    years(e, 2)
    assert {x.payload["status"] for x in of(e, "beat.mourned")} == {"dead"}
    assert e.check_conservation() == []


def write(tmp_path, monkeypatch, name, body):
    (tmp_path / f"{name}.py").write_text(textwrap.dedent(body), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    e = renascita.new_engine(seed=3)
    return e


HEAD = """
    from renasci.core.events import EventType
    from renasci.core.pools import Reaction

    BEAT = EventType("beat.x", 1, roles={"who": (1, 1)}, payload={}, dead_roles=("who",))
"""


@pytest.mark.parametrize("body, wrong", [
    ('''
    def run(ctx, event):
        ctx.emit("beat.x", {"who": event.roles["deceased"]}, purpose="x", actor="t:x")

    def extend(pools):
        pools.event_types.add(BEAT)
        pools.reactions.add(Reaction("r", "people.death", run))
    ''', "without declaring"),
    ('''
    from renasci.core.calendar import Span

    def run(ctx, event):
        ctx.schedule(Span(days=1), "later")

    def extend(pools):
        pools.reactions.add(Reaction("r", "people.death", run))
    ''', "can't schedule"),
])
def test_a_reaction_keeps_to_what_it_declares(tmp_path, monkeypatch, body, wrong):
    from renasci.core.engine import UndeclaredAccess

    e = write(tmp_path, monkeypatch, "ext_bad", HEAD + body)
    e.extend(["ext_bad"])
    with pytest.raises((ValueError, UndeclaredAccess), match=wrong):
        years(e, 3)
    sys.modules.pop("ext_bad", None)


@pytest.mark.parametrize("on", ["people.nothing", "ripple.protect", "engine.cast"])
def test_a_reaction_to_what_can_never_come_is_refused(tmp_path, monkeypatch, on):
    e = write(tmp_path, monkeypatch, "ext_never", HEAD + f'''
    def extend(pools):
        pools.reactions.add(Reaction("r", "{on}", print))
    ''')
    with pytest.raises(ValueError):
        e.extend(["ext_never"])
    sys.modules.pop("ext_never", None)


def test_reactions_replay_identically(ext):
    a, b = (renascita.new_engine(seed=3) for _ in range(2))
    a.extend([ext]), b.extend([ext])
    years(a, 2), years(b, 2)
    assert [x.id for x in a.events] == [x.id for x in b.events]


def test_a_reaction_loop_is_refused(tmp_path, monkeypatch):
    (tmp_path / "ext_loop.py").write_text(textwrap.dedent("""
        from renasci.core.events import EventType
        from renasci.core.pools import Reaction

        AGAIN = EventType("beat.again", 1, roles={"who": (1, 1)}, payload={}, dead_roles=("who",))

        def again(ctx, event):
            who = event.roles.get("who", event.roles.get("deceased"))[0]
            ctx.emit("beat.again", {"who": (who,)}, purpose="again", actor=who)

        def extend(pools):
            pools.event_types.add(AGAIN)
            pools.reactions.add(Reaction("start", "people.death", again, emits=("beat.again",)))
            pools.reactions.add(Reaction("again", "beat.again", again, emits=("beat.again",)))
    """), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    e = renascita.new_engine(seed=3)
    e.extend(["ext_loop"])
    with pytest.raises(ValueError, match="a loop"):
        years(e, 3)
    sys.modules.pop("ext_loop", None)
