"""#152: the S1 additions S3 needs (S3 spec §15).

- keyed binomial / multinomial / hypergeometric draws
- several columns in one write (one bulk delta), and promote/demote over several columns
- birth pins: a pin binds a canon id to the natural entity that fulfils it; roles resolve through
  bindings; an existence pin for a bound subject is not cast up front
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.engine import Engine
from renasci.core.events import EventType
from renasci.core.pins import Forcer, Pin
from renasci.core.rng import Stream
from renasci.core.systems import Ruleset, System
from renasci.core.lod import EVENT_TYPES as LOD_TYPES
from renasci.toy import BIRTH, new_engine

# ---------------------------------------------------------------- draws


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 2**40), st.integers(0, 500), st.floats(0, 1))
def test_binomial_is_keyed_and_bounded(key, n, p):
    a, b = Stream(key).binomial(n, p), Stream(key).binomial(n, p)
    assert a == b and isinstance(a, int) and 0 <= a <= n


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 2**40), st.integers(0, 500), st.lists(st.floats(0.01, 1), min_size=1, max_size=6))
def test_multinomial_shares_out_exactly_n(key, n, weights):
    pvals = [w / sum(weights) for w in weights]
    out = Stream(key).multinomial(n, pvals)
    assert out == Stream(key).multinomial(n, pvals) and sum(out) == n and all(isinstance(x, int) for x in out)


@settings(max_examples=60, deadline=None)
@given(st.integers(0, 2**40), st.lists(st.integers(0, 50), min_size=1, max_size=6), st.data())
def test_hypergeometric_draws_without_replacement(key, colours, data):
    nsample = data.draw(st.integers(0, sum(colours)))
    out = Stream(key).hypergeometric(colours, nsample)
    assert out == Stream(key).hypergeometric(colours, nsample)
    assert sum(out) == nsample and all(0 <= o <= c for o, c in zip(out, colours))


@pytest.mark.parametrize("call", [
    lambda s: s.binomial(-1, 0.5), lambda s: s.binomial(3, 1.5), lambda s: s.binomial(2.5, 0.5),
    lambda s: s.multinomial(3, [0.5, 0.6]), lambda s: s.multinomial(3, [-0.1, 1.1]),
    lambda s: s.hypergeometric([3, 2], 6), lambda s: s.hypergeometric([3, -1], 1),
])
def test_bad_draw_arguments_are_refused(call):
    with pytest.raises(ValueError):
        call(Stream(1))


# ---------------------------------------------------------------- many columns at once

CAL_START = Date(1, 1, 0)
TICK = EventType("mini.tick", 1, roles={}, payload={})


def column_engine(system):
    from renasci.toy import CAL

    e = Engine(CAL, seed=1, rulesets=[(CAL_START, Ruleset("c", 1, (system,)))])
    e.cast("place", "t:town", {})
    e.cast_column("pop:a", "int64", ["t:town"], [5])
    e.cast_column("pop:b", "int64", ["t:town"], [7])
    return e


class Census(System):
    name, cadence = "mini.census", "yearly"
    reads = frozenset({"pop:a", "pop:b"})
    writes = frozenset({"pop:a", "pop:b"})
    event_types = (TICK,)

    def run(self, ctx):
        with ctx.scope("t:town"):
            ctx.emit("mini.tick", {}, purpose="census", actor="t:town")
            a, b = (int(ctx.read_column(c, ["t:town"])[0]) for c in ("pop:a", "pop:b"))
            ctx.write_columns("t:town", {"pop:a": a + 1, "pop:b": b + 2})


def test_write_columns_is_one_bulk_delta_for_many_columns():
    e = column_engine(Census())
    e.run(until=Date(1, 1, 359))
    rows = [d.to_json() for d in e.store.bulk_deltas]
    mine = [r for r in rows if r.get("components")]
    assert len(mine) == 1 and mine[0]["components"] == ["pop:a", "pop:b"] and "component" not in mine[0]
    assert list(e.store.read_column("pop:a", ["t:town"])) == [6] and list(e.store.read_column("pop:b", ["t:town"])) == [9]


def test_divergence_attributes_multi_column_writes_to_each_cell():
    a, b = column_engine(Census()), column_engine(Census())
    for e in (a, b):
        e.run(until=Date(1, 2, 359))
    report = analyse(a.pending(), b.pending(), a.store.to_json(), b.store.to_json())
    assert report["divergent_cells"] == 0  # and it parsed the multi-column rows without error


class Mover(System):
    """Promotes one person out of the town, taking from two columns, then demotes them back."""

    name, cadence = "mini.mover", "yearly"
    reads = frozenset({"pop:a", "pop:b", "status"})
    writes = frozenset({"pop:a", "pop:b", "new:person", "status"})
    event_types = LOD_TYPES

    def run(self, ctx):
        with ctx.scope("t:town"):
            if ctx.today.year == 1:
                Mover.who = ctx.promote("t:town", "person", {"sex": "f"}, reason="test",
                                        columns={"pop:a": 1, "pop:b": 2})
            else:
                ctx.demote(Mover.who, reason="test", aggregate="t:town", columns={"pop:a": 1, "pop:b": 2})


def test_promote_and_demote_over_several_columns_round_trip():
    e = column_engine(Mover())
    e.run(until=Date(1, 1, 359))
    assert [int(e.store.read_column(c, ["t:town"])[0]) for c in ("pop:a", "pop:b")] == [4, 5]
    e.run(until=Date(1, 2, 359))
    assert [int(e.store.read_column(c, ["t:town"])[0]) for c in ("pop:a", "pop:b")] == [5, 7]
    assert e.store.status(Mover.who) == "dormant"


class Greedy(System):
    name, cadence = "mini.greedy", "yearly"
    event_types = LOD_TYPES
    reads = frozenset({"pop:a", "pop:b"})
    writes = frozenset({"pop:a", "pop:b", "new:person"})

    def run(self, ctx):
        with ctx.scope("t:town"):
            ctx.promote("t:town", "person", {}, reason="test", columns={"pop:a": 1, "pop:b": 8})


def test_promote_refuses_before_changing_anything_when_a_column_runs_short():
    e = column_engine(Greedy())
    with pytest.raises(ValueError, match="pop:b"):
        e.run(until=Date(1, 1, 359))
    assert [int(e.store.read_column(c, ["t:town"])[0]) for c in ("pop:a", "pop:b")] == [5, 7]


# ---------------------------------------------------------------- birth pins (toy world)

END = Date(1, 12, 359)


@pytest.fixture(scope="module")
def baseline():
    e = new_engine(people_per_village=8)
    e.run(until=END)
    births = [ev for ev in e.events if ev.type == "toy.birth" and ev.date.year >= 3]
    assert births, "the toy needs a natural birth to pin"
    return e, births[0]


def birth_pin(birth, subject="v:Kid", sex=None, window=None):
    w = window or (Date(1, birth.date.year, 0), Date(1, birth.date.year, 359))
    bind = {"role": "child", "subject": subject} | ({"fields": {"sex": sex}} if sex else {})
    return Pin("p_kid", "event", window=w, payload={"type": "toy.birth",
                                                   "roles": {"mother": list(birth.roles["mother"])}, "bind": bind})


def test_a_birth_pin_met_naturally_binds_the_canon_id_and_changes_nothing(baseline):
    base, birth = baseline
    child = birth.roles["child"][0]
    e = new_engine(people_per_village=8, pins=[birth_pin(birth),
                                               Pin("p_kid_exists", "existence", subject="v:Kid")])
    assert not e.store.exists("v:Kid")  # born during the run: never cast up front
    e.run(until=END)
    assert e.director.bindings == {"v:Kid": child}
    assert e.director.status["p_kid"] == "satisfied" and e.director.status["p_kid_exists"] == "satisfied"
    assert e.director.strain == []
    assert [ev.to_json() for ev in e.events] == [ev.to_json() for ev in base.events]  # a pure observer
    assert any(row.get("binding") == {"v:Kid": child} for row in e.pending()["pins"])


def test_a_birth_of_the_wrong_sex_does_not_fulfil_the_pin(baseline):
    base, birth = baseline
    child = birth.roles["child"][0]
    other = "m" if base.store.get(child, "sex") == "f" else "f"
    e = new_engine(people_per_village=8, pins=[birth_pin(birth, sex=other)])
    e.run(until=END)
    assert e.director.bindings.get("v:Kid") != child


def test_roles_resolve_through_bindings_so_a_bound_parent_is_guarded(baseline):
    base, birth = baseline
    child = birth.roles["child"][0]
    later = Pin("p_grandkid", "event", window=(Date(1, birth.date.year + 1, 0), Date(1, 40, 0)),
                payload={"type": "toy.birth", "roles": {"mother": ["v:Kid"]}})
    e = new_engine(people_per_village=8, pins=[birth_pin(birth), later])
    e.run(until=END)
    assert e.director.guard_pin(child, Date(1, birth.date.year + 2, 0)).id == "p_grandkid"


class ForceBirth(Forcer):
    name = "mini.force_birth"
    handles = "toy.birth"
    event_types = (BIRTH,)
    reads = frozenset({"village"})
    writes = frozenset({"new:person"})

    def force(self, ctx, pin):
        mother = pin.payload["roles"]["mother"][0]
        ctx.emit("toy.birth", {"mother": (mother,)}, purpose="forced_birth", actor=mother,
                 creates={"child": [("person", {"sex": "m", "born": ctx.today.year,
                                                "village": ctx.get(mother, "village"), "spouse": None})]})
        return True


def test_an_unmet_birth_pin_is_forced_and_binds_the_forced_child(baseline):
    from renasci.toy import START, ruleset

    rs = ruleset()
    rs = Ruleset(rs.name, rs.version, rs.systems, rs.params, forcers=(ForceBirth(),))
    e = new_engine(people_per_village=8)
    e.rulesets = [(START, rs)]
    mother = "t:Ashford-01"
    e.apply_pins([Pin("p_kid", "event", window=(Date(1, 2, 0), Date(1, 2, 10)),
                      payload={"type": "toy.birth", "roles": {"mother": [mother]},
                               "bind": {"role": "child", "subject": "v:Kid"}})])
    e.run(until=Date(1, 3, 0))
    assert e.director.status["p_kid"] == "forced"
    kid = e.director.bindings["v:Kid"]
    assert e.store.get(kid, "sex") == "m" and [s["action"] for s in e.director.strain] == ["force"]


def test_bindings_survive_a_checkpoint(baseline):
    base, birth = baseline
    e = new_engine(people_per_village=8, pins=[birth_pin(birth)])
    e.run(until=END)
    from renasci.core.pins import Director

    d = Director(e.director.pins)
    d.load_json(e.director.to_json())
    assert d.bindings == e.director.bindings


# ---------------------------------------------------------------- review fixes


def test_draws_match_a_golden_vector():
    """Catches drift across platforms and NumPy versions (they use libm inside NumPy)."""
    s = Stream(20261022)
    got = [s.binomial(40, 0.3), s.binomial(1000, 0.01), s.multinomial(30, [0.2, 0.3, 0.5]),
           s.hypergeometric([10, 5, 20], 12)]
    assert got == GOLDEN_DRAWS


GOLDEN_DRAWS = [13, 10, [6, 10, 14], [7, 1, 4]]  # NumPy 2.5, Philox


@pytest.mark.parametrize("columns", [{"pop:a": 0.5}, {"pop:a": True}, {"pop:a": -1}])
def test_promote_rejects_non_count_amounts_before_anything_happens(columns):
    class Odd(System):
        name, cadence = "mini.odd", "yearly"
        reads = frozenset({"pop:a"})
        writes = frozenset({"pop:a", "new:person"})
        event_types = LOD_TYPES

        def run(self, ctx):
            with ctx.scope("t:town"):
                ctx.promote("t:town", "person", {}, reason="test", columns=columns)

    e = column_engine(Odd())
    with pytest.raises(ValueError):
        e.run(until=Date(1, 1, 359))
    assert e.events == [] or all(ev.type != "lod.promote" for ev in e.events)
    assert int(e.store.read_column("pop:a", ["t:town"])[0]) == 5


def test_a_birth_pin_outside_the_run_falls_back_to_casting():
    late = Pin("p_kid", "event", window=(Date(1, 500, 0), Date(1, 501, 0)),
               payload={"type": "toy.birth", "roles": {}, "bind": {"role": "child", "subject": "v:Kid"}})
    e = new_engine(people_per_village=4, pins=[late, Pin("p_kid_exists", "existence", subject="v:Kid")])
    assert e.director.status["p_kid"] == "out_of_scope"
    assert e.store.exists("v:Kid") and e.director.status["p_kid_exists"] == "satisfied"


def test_a_violated_birth_pin_violates_existence_on_its_subject():
    e = new_engine(people_per_village=4, pins=[
        Pin("p_kid", "event", window=(Date(1, 2, 0), Date(1, 2, 10)),
            payload={"type": "toy.birth", "roles": {"mother": ["t:Ashford-01"]},
                     "bind": {"role": "child", "subject": "v:Kid"}}),
        Pin("p_kid_exists", "existence", subject="v:Kid")])
    e.run(until=Date(1, 3, 0))  # the toy has no forcer for births
    assert e.director.status["p_kid"] == "violated" and e.director.status["p_kid_exists"] == "violated"


@pytest.mark.parametrize("payload, message", [
    ({"type": "toy.birth", "roles": {}, "bind": {"role": "child", "subject": "Kid"}}, "v:"),
    ({"type": "toy.birth", "roles": {"child": ["x"]}, "bind": {"role": "child", "subject": "v:Kid"}}, "role"),
    ({"type": "toy.birth", "roles": {}, "bind": {"role": "child", "subject": "v:Kid", "fields": {"sex": None}}},
     "None"),
])
def test_bind_shapes_are_checked(payload, message):
    with pytest.raises(ValueError, match=message):
        Pin("p", "event", window=(Date(1, 2, 0), Date(1, 3, 0)), payload=payload)


def test_two_pins_cannot_bind_the_same_subject():
    from renasci.core.pins import Director

    bind = {"type": "toy.birth", "roles": {}, "bind": {"role": "child", "subject": "v:Kid"}}
    with pytest.raises(ValueError, match="v:Kid"):
        Director([Pin("a", "event", window=(Date(1, 2, 0), Date(1, 3, 0)), payload=bind),
                  Pin("b", "event", window=(Date(1, 4, 0), Date(1, 5, 0)), payload=bind)])


# ---------------------------------------------------------------- #71/#72 review: protected, read_columns, declarations


def test_protected_asks_without_taking_the_protector_as_a_cause():
    from renasci.core.ripples import Ripple

    seen = {}

    class Asker(System):
        name, cadence = "mini.asker", "yearly"
        reads = frozenset()
        event_types = (TICK,)

        def run(self, ctx):
            with ctx.scope("t:town"):
                seen["protected"] = ctx.protected("t:town")
                seen["event"] = ctx.emit("mini.tick", {}, purpose="tick", actor="t:town")

    e = column_engine(Asker())
    e.apply_ripples([Ripple("r1", "protect", Date(1, 1, 0), "t:town", {"until": [1, 3, 0]})])
    e.run(until=Date(1, 1, 359))
    assert seen["protected"] is True
    assert ("ripple", "r1") not in [(c.kind, c.ref) for c in seen["event"].causes]
    assert not [r for r in e.ripple_log if r.get("action") == "guard"]
    assert any(["t:town", "guard"] == r[:2] for row in e.reads for r in row.get("reads", []))  # still a recorded read


def test_read_columns_reads_many_and_records_them():
    got = {}

    class Reader(System):
        name, cadence = "mini.reader", "yearly"
        reads = frozenset({"pop:*"})
        event_types = (TICK,)

        def run(self, ctx):
            with ctx.scope("t:town"):
                got.update(ctx.read_columns("t:town", ["pop:a", "pop:b"]))

    e = column_engine(Reader())
    e.run(until=Date(1, 1, 359))
    assert got == {"pop:a": 5, "pop:b": 7}
    assert any(r[0] == "t:town" and r[1].startswith("columns:") for row in e.reads for r in row.get("reads", []))


def test_a_bare_star_declaration_is_refused():
    class Greedy(System):
        name, cadence = "mini.star", "yearly"
        reads = frozenset({"*"})

    with pytest.raises(ValueError, match=r"\*"):
        Greedy().check()
