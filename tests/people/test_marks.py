"""Marks (#163): what a thing has become, from what happened to it."""

import contextlib
import pathlib
import re
import types

from renasci import ecology, marks, renascita
from renasci.core.calendar import Date, Span
from renasci.core.pools import load
from renasci.people.ambitions import trait


def world(**eco):
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}, **eco}
    return sc


def run(sc, seed=3, years=6):
    e = renascita.new_engine(seed=seed, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=years)))
    return e


def of(e, t):
    return [x for x in e.events if x.type == t]


class Ctx:
    """Just enough of a ctx for the pure parts."""

    def __init__(self, traits=None):
        self.fields, self.params = {}, {"traits": traits or {}}

    def get(self, entity, field, default=None):
        return self.fields.get((entity, field), default)

    def set(self, entity, field, value):
        self.fields[(entity, field)] = value


def test_a_mark_needs_all_it_names():
    ctx = Ctx()
    mark = marks.Mark("m", "m", ("person",), {"a": 2, "b": 1})
    ctx.fields[("p", "level:a")] = 2.0
    assert not marks.met(ctx, "p", mark)
    ctx.fields[("p", "level:b")] = 1.0
    assert marks.met(ctx, "p", mark)


def test_needs_can_read_fame_and_the_skill_of_ones_job():
    ctx = Ctx()
    ctx.fields.update({("o", "fame"): 0.6, ("p", "job"): "smith", ("p", "skills"): {"smith": 0.95, "cook": 0.1}})
    assert marks.reading(ctx, "o", "fame") == 0.6 and marks.reading(ctx, "p", "skill") == 0.95


def test_a_mark_on_a_person_moves_the_trait_their_odds_read_and_can_be_undone():
    ctx = Ctx({"wits": "stature"})
    ctx.fields[("p", "traits")] = {"stature": 0.9}
    moved = marks._apply(ctx, "person", "p", {"wits": 0.3})
    assert trait(ctx, "p", "wits") == 1.0 and moved == {"wits": 0.1}  # (capped, and only what moved is recorded)
    marks._apply(ctx, "person", "p", moved, -1)
    assert trait(ctx, "p", "wits") == 0.9


def test_a_mark_on_anything_else_moves_its_field():
    ctx = Ctx()
    moved = marks._apply(ctx, "settlement", "s", {"danger": 0.2})
    assert ctx.get("s", "danger") == 0.2 and moved == {"danger": 0.2}


class Yearly(Ctx):
    """Enough of a ctx to run the system itself: every draw lands."""

    today = Date(4, 10, 0)
    current_event = "e0"

    def __init__(self, things):
        super().__init__()
        self.pools, self.things, self.emitted = load(), things, []

    def ids(self, kind, status=None):
        return self.things.get(kind, [])

    def scope(self, key):
        return contextlib.nullcontext()

    def status(self, entity):
        return "active"

    def chance(self, p, purpose, owner=None):
        return True

    def emit(self, type, roles, **kw):
        self.emitted.append((type, kw["payload"]["mark"]))
        return types.SimpleNamespace(id=f"e{len(self.emitted)}")


def test_a_sword_turns_from_its_deeds():
    ctx = Yearly({"object": ["o"]})
    ctx.fields.update({("o", "level:blood"): 3.0, ("o", "why:blood"): {"deed": 3.0}, ("o", "fame"): 0.5})
    marks.Marks().step(ctx, 1)
    assert ctx.emitted == [("mark.gained", "bloodthirsty")]
    assert ctx.get("o", "fame") == 0.7 and ctx.get("o", "acquired")[0]["id"] == "bloodthirsty"
    marks.Marks().step(ctx, 1)
    assert len(ctx.emitted) == 1  # (once)


def test_a_fading_mark_goes_and_puts_back_what_it_moved():
    ctx = Yearly({"settlement": ["s"]})
    ctx.fields.update({("s", "level:corpses"): 200.0, ("s", "danger"): 0.1})
    marks.Marks().step(ctx, 1)
    assert ctx.get("s", "danger") == 0.3
    ctx.fields[("s", "level:corpses")] = 100.0  # (half: it holds)
    marks.Marks().step(ctx, 1)
    assert ctx.get("s", "danger") == 0.3
    ctx.fields[("s", "level:corpses")] = 10.0
    marks.Marks().step(ctx, 1)
    assert ctx.emitted[-1] == ("mark.lost", "haunted")
    assert ctx.get("s", "danger") == 0.1 and not ctx.get("s", "acquired")


def test_time_eases_a_mark_though_nothing_drains_it():
    ctx = Yearly({"settlement": ["s"]})
    ctx.params["traits"] = {"temper": "temper", "charm": "charm"}
    ctx.fields.update({("s", "residents"): ["p"], ("p", "level:dread"): 2.0, ("p", "traits"): {"temper": 0.5, "charm": 0.5}})
    marks.Marks().step(ctx, 1)
    assert ctx.emitted == [("mark.gained", "shaken")] and ctx.get("p", "traits")["temper"] == 0.7
    ctx.today = Date(4, 16, 0)
    marks.Marks().step(ctx, 1)
    assert ctx.emitted[-1] == ("mark.lost", "shaken")
    assert ctx.get("p", "traits") == {"temper": 0.5, "charm": 0.5}


def test_a_role_the_world_does_not_map_does_nothing():
    ctx = Ctx({"temper": "stature"})
    ctx.fields[("p", "traits")] = {"stature": 0.5}
    assert marks._apply(ctx, "person", "p", {"temper": 0.1, "charm": 0.1}) == {"temper": 0.1}
    assert ctx.get("p", "traits") == {"stature": 0.6}


def test_a_coarse_step_gives_a_mark_its_years_of_chances():
    class Draws(Yearly):
        def chance(self, p, purpose, owner=None):
            self.p = p
            return False

    ctx = Draws({"object": ["o"]})
    ctx.fields[("o", "level:blood")] = 5.0
    marks.Marks().step(ctx, 5)
    assert ctx.p > 0.6


def test_a_fame_mark_cites_the_deeds_behind_it():
    mark = marks.Mark("storied", "storied", ("object",), {"fame": 0.5})
    ctx = Yearly({"object": ["o"]})
    ctx.fields.update({("o", "fame"): 0.5, ("o", "deeds"): ["d1", "d2"]})
    assert [c.ref for c in marks.why(ctx, "o", mark)] == ["d1", "d2"]


def test_a_mark_declares_what_it_moves():
    mark = marks.Mark("x", "x", ("polity",), {"a": 1}, {"morale": 0.1})
    assert mark.reads == {"morale"} and mark.writes == {"morale"}


def test_one_mark_can_need_another():
    mark = marks.Mark("cursed", "cursed", ("object",), {"blood": 1}, pre=("bloodthirsty",))
    ctx = Yearly({"object": ["o"]})
    ctx.pools = types.SimpleNamespace(marks={"cursed": mark})
    ctx.fields[("o", "level:blood")] = 5.0
    marks.Marks().step(ctx, 1)
    assert not ctx.emitted
    ctx.fields[("o", "acquired")] = [{"id": "bloodthirsty"}]
    marks.Marks().step(ctx, 1)
    assert ctx.emitted == [("mark.gained", "cursed")]


def test_a_town_is_haunted_by_the_dead_it_cannot_clear_and_it_cites_them():
    sc = world(burial={"bury": 0, "rot": 0, "winter": 0})
    e = run(sc, years=8)
    gained = [x for x in of(e, "mark.gained") if x.payload["mark"] == "haunted"]
    assert gained
    town = gained[0].roles["subject"][0]
    assert e.store.get(town, "danger") >= 0.2
    assert [c for c in gained[0].causes if c.kind == "event"]


def test_a_town_that_buries_its_dead_is_not_haunted():
    cleared = run(world(), years=8)
    assert not [x for x in of(cleared, "mark.gained") if x.payload["mark"] == "haunted"]
    assert cleared.check_conservation() == []


def test_no_system_that_feeds_a_mark_names_one():
    src = pathlib.Path(marks.__file__).parent
    for name in ("ecology.py", "people/crafts.py", "people/life.py", "people/population.py", "campaigns.py"):
        text = (src / name).read_text(encoding="utf-8")
        assert not any(re.search(rf"\b{m}\b", text) for m in marks.MARKS), name


def test_an_extension_can_add_a_mark(tmp_path, monkeypatch):
    import sys
    import textwrap

    (tmp_path / "ext_marks.py").write_text(textwrap.dedent("""
        from renasci.marks import Mark

        def extend(pools):
            pools.marks.add(Mark("cursed", "cursed", ("object",), {"blood": 1}, pre=("bloodthirsty",)))
    """), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert "cursed" in load(["ext_marks"]).marks and "cursed" not in marks.MARKS
    sys.modules.pop("ext_marks", None)


def test_marks_can_be_switched_off():
    sc = world()
    sc["params"]["marks"] = False
    assert "marks.change" not in {s.name for s in renascita.rulesets(sc)[0][1].systems}
