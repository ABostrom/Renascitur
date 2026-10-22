import pytest
from hypothesis import given
from hypothesis import strategies as st

from renasci.core.calendar import Date
from renasci.core.canon import canonical
from renasci.core.events import Cause, CauseIndex, Event, EventType, Registry, Source
from renasci.core.store import Store

D = Date(4, 37, 10)

MARRIAGE = EventType(
    "toy.marriage", 1,
    roles={"spouse": (2, 2), "witness": (0, 3)},
    payload={"dowry": "int", "village": "id"},
)
POISONING = EventType("toy.poisoning", 1, roles={"poisoner": (1, 1), "victim": (1, 1)}, payload={}, visibility="secret")
ILLNESS = EventType("toy.illness_death", 1, roles={"deceased": (1, 1)}, payload={"illness": "str"})


def registry():
    r = Registry()
    for t in (MARRIAGE, POISONING, ILLNESS):
        r.register(t)
    return r


def marriage(**over):
    base = dict(
        id="x1", date=D, type="toy.marriage",
        roles={"spouse": ("e1", "e2")}, place="t:Millbrook",
        causes=(Cause("event", "x0"),), payload={"dowry": 3, "village": "t:Millbrook"},
        source=Source("system", "toy.marriage"),
    )
    base.update(over)
    return Event(**base)


# ---------------------------------------------------------------- registry and schema


def test_register_twice_is_an_error():
    r = registry()
    with pytest.raises(ValueError):
        r.register(MARRIAGE)


def test_valid_event_passes_and_takes_default_visibility():
    r = registry()
    e = r.validate(marriage())
    assert e.visibility == "public"


@pytest.mark.parametrize(
    "over",
    [
        dict(type="toy.unknown"),
        dict(roles={"spouse": ("e1",)}),  # too few
        dict(roles={"spouse": ("e1", "e2"), "witness": ("a", "b", "c", "d")}),  # too many
        dict(roles={"spouse": ("e1", "e2"), "groom": ("e3",)}),  # unknown role
        dict(roles={"spouse": ("e1", "e1")}),  # same entity twice in a role
        dict(payload={"dowry": "3", "village": "t:Millbrook"}),  # wrong type
        dict(payload={"dowry": 3}),  # missing field
        dict(payload={"dowry": 3, "village": "t:Millbrook", "extra": 1}),  # unknown field
        dict(payload={"dowry": True, "village": "t:Millbrook"}),  # bool is not int
        dict(causes=(Cause("event", "x1"),)),  # an event cannot cause itself
    ],
)
def test_schema_violations_are_rejected(over):
    with pytest.raises((ValueError, TypeError)):
        registry().validate(marriage(**over))


@pytest.mark.parametrize("bad", [lambda: Cause("rumour", "x"), lambda: Cause("event", ""), lambda: Source("magic", "x")])
def test_cause_and_source_kinds_are_checked(bad):
    with pytest.raises(ValueError):
        bad()


def test_visibility_must_be_known():
    with pytest.raises(ValueError):
        registry().validate(marriage(visibility="whispered"))


def test_dead_participants_are_rejected():
    store = Store()
    store.create("person", "e1", {}, D, "x0")
    store.create("person", "e2", {}, D, "x0")
    store.create("place", "t:Millbrook", {}, D, "x0")
    store.set_status("e2", "dead", D, "x0")
    with pytest.raises(ValueError):
        registry().validate(marriage(), store=store)


def test_dead_participant_allowed_in_a_role_marked_for_the_dead():
    funeral = EventType("toy.funeral", 1, roles={"deceased": (1, 1), "mourner": (0, 9)}, payload={},
                        dead_roles=("deceased",))
    r = Registry()
    r.register(funeral)
    store = Store()
    store.create("person", "e1", {}, D, "x0")
    store.set_status("e1", "dead", D, "x0")
    r.validate(Event("x5", D, "toy.funeral", {"deceased": ("e1",)}, None, (), {}, Source("system", "toy.life")), store=store)


def test_event_must_be_dated_today_when_today_is_given():
    with pytest.raises(ValueError):
        registry().validate(marriage(), today=Date(4, 37, 11))


# ---------------------------------------------------------------- JSON


def test_event_json_is_canonical_and_round_trips():
    e = registry().validate(marriage(roles={"witness": ("e9",), "spouse": ("e2", "e1")}))
    j = e.to_json()
    assert list(j["roles"]) == ["spouse", "witness"]
    assert j["roles"]["spouse"] == ["e1", "e2"]  # members sorted
    assert Event.from_json(j) == e
    assert canonical(Event.from_json(j).to_json()) == canonical(j)


def test_participants_lists_every_entity_once_sorted():
    e = marriage(roles={"spouse": ("e2", "e1"), "witness": ("e3",)})
    assert e.participants() == ["e1", "e2", "e3"]


# ---------------------------------------------------------------- secret events and covers


def test_secret_event_and_its_public_cover_are_linked_by_a_cause():
    r = registry()
    secret = r.validate(Event("xs", D, "toy.poisoning", {"poisoner": ("e1",), "victim": ("e2",)}, None, (), {},
                              Source("action", "poison")))
    cover = r.validate(Event("xc", D, "toy.illness_death", {"deceased": ("e2",)}, None,
                             (Cause("event", "xs"),), {"illness": "a wasting illness"}, Source("action", "poison")))
    assert secret.visibility == "secret" and cover.visibility == "public"
    idx = CauseIndex()
    idx.add(secret)
    idx.add(cover)
    assert idx.ancestors(("event", "xc")) == [("event", "xs")]


# ---------------------------------------------------------------- cause index


def chain():
    idx = CauseIndex()
    idx.add(Event("x1", D, "t", {}, None, (Cause("ripple", "r1"),), {}, Source("ripple", "r1")))
    idx.add(Event("x2", D, "t", {}, None, (Cause("event", "x1"), Cause("pin", "p1")), {}, Source("system", "s")))
    idx.add(Event("x3", D, "t", {}, None, (Cause("event", "x2"),), {}, Source("system", "s")))
    idx.add(Event("x4", D, "t", {}, None, (Cause("event", "x1"),), {}, Source("system", "s")))
    return idx


def test_descendants_and_ancestors_both_ways():
    idx = chain()
    assert idx.descendants(("ripple", "r1")) == [("event", "x1"), ("event", "x2"), ("event", "x3"), ("event", "x4")]
    assert idx.descendants(("event", "x1"), depth=1) == [("event", "x2"), ("event", "x4")]
    assert idx.ancestors(("event", "x3")) == [("event", "x1"), ("event", "x2"), ("pin", "p1"), ("ripple", "r1")]
    assert idx.ancestors(("event", "x3"), depth=1) == [("event", "x2")]


def test_index_refuses_an_event_twice():
    idx = chain()
    with pytest.raises(ValueError):
        idx.add(Event("x3", D, "t", {}, None, (), {}, Source("system", "s")))


def test_index_json_round_trip_is_order_independent():
    idx = chain()
    again = CauseIndex.from_json(idx.to_json())
    assert again.to_json() == idx.to_json()
    assert again.descendants(("ripple", "r1")) == idx.descendants(("ripple", "r1"))


@given(st.permutations(["x1", "x2", "x3", "x4"]))
def test_edges_json_is_sorted(order):
    events = {e: Event(e, D, "t", {}, None, (Cause("ripple", "r0"),), {}, Source("system", "s")) for e in order}
    a, b = CauseIndex(), CauseIndex()
    for e in order:
        a.add(events[e])
    for e in sorted(order):
        b.add(events[e])
    assert a.to_json() == b.to_json()


# ---------------------------------------------------------------- review fixes


def ev(eid, *causes, source=("system", "s")):
    return Event(eid, D, "t", {}, None, tuple(Cause(*c) for c in causes), {}, Source(*source))


def test_index_requires_event_causes_to_exist_first_so_it_stays_acyclic():
    idx = CauseIndex()
    with pytest.raises(ValueError):
        idx.add(ev("a", ("event", "b")))
    idx.add(ev("b"))
    idx.add(ev("a", ("event", "b")))
    assert idx.ancestors(("event", "a")) == [("event", "b")]


def test_index_from_json_rejects_unknown_event_causes():
    with pytest.raises(ValueError):
        CauseIndex.from_json({"events": ["a"], "edges": [["a", "event", "zzz"]]})


def test_index_json_restores_when_child_sorts_before_parent():
    idx = CauseIndex()
    idx.add(ev("x9"))
    idx.add(ev("x1", ("event", "x9")))
    assert CauseIndex.from_json(idx.to_json()).ancestors(("event", "x1")) == [("event", "x9")]


def test_role_members_must_be_a_list_or_tuple():
    with pytest.raises(TypeError):
        marriage(roles={"spouse": "al"})


def test_duplicate_causes_are_rejected():
    with pytest.raises(ValueError):
        registry().validate(marriage(causes=(Cause("event", "x0"), Cause("event", "x0"))))


def test_empty_roles_and_int_floats_have_one_canonical_form():
    t = EventType("toy.harvest", 1, roles={"farmer": (0, 5)}, payload={"yield": "float"})
    r = Registry()
    r.register(t)
    a = r.validate(Event("x1", D, "toy.harvest", {"farmer": ()}, None, (), {"yield": 1}, Source("system", "s")))
    b = r.validate(Event("x1", D, "toy.harvest", {}, None, (), {"yield": 1.0}, Source("system", "s")))
    assert canonical(a.to_json()) == canonical(b.to_json())


def test_ripple_and_pin_sources_are_indexed_as_causes():
    idx = CauseIndex()
    idx.add(ev("x1", source=("ripple", "r1")))
    idx.add(ev("x2", source=("pin", "p1")))
    assert idx.descendants(("ripple", "r1")) == [("event", "x1")]
    assert idx.descendants(("pin", "p1")) == [("event", "x2")]


def test_place_and_id_payloads_must_exist_when_a_store_is_given():
    store = Store()
    store.create("person", "e1", {}, D, "x0")
    store.create("person", "e2", {}, D, "x0")
    with pytest.raises(ValueError):  # place t:Millbrook missing
        registry().validate(marriage(payload={"dowry": 3, "village": "e1"}), store=store)
    store.create("place", "t:Millbrook", {}, D, "x0")
    with pytest.raises(ValueError):  # payload id missing
        registry().validate(marriage(payload={"dowry": 3, "village": "t:Nowhere"}), store=store)
    registry().validate(marriage(), store=store)


def test_validated_events_record_their_schema_version():
    e = registry().validate(marriage())
    assert e.version == 1
    assert e.to_json()["version"] == 1
    assert Event.from_json(e.to_json()) == e
