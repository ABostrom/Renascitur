import pytest
from hypothesis import given
from hypothesis import strategies as st

from renasci.core.calendar import Age, AgeBoundaryError, Calendar, Date
from renasci.core.events import Cause
from renasci.core.scheduler import Activation, Scheduler, next_due

CAL = Calendar(ages=(Age(1, "1X", "Toy Age", last_year=300),))


def act(day=0, priority=0, entity="e1", purpose="tick", system="toy.life", payload=None, causes=(), year=1):
    return Activation(Date(1, year, day), priority, entity, purpose, system, payload or {}, causes)


# ---------------------------------------------------------------- ordering


def test_pops_in_total_order_date_priority_entity_purpose_system():
    s = Scheduler()
    items = [
        act(day=5),
        act(day=1, priority=2),
        act(day=1, priority=1, entity="e2"),
        act(day=1, priority=1, entity="e1", purpose="z"),
        act(day=1, priority=1, entity="e1", purpose="a", system="toy.b"),
        act(day=1, priority=1, entity="e1", purpose="a", system="toy.a"),
    ]
    for a in items:
        s.push(a)
    popped = [s.pop() for _ in items]
    assert popped == [items[5], items[4], items[3], items[2], items[1], items[0]]


@given(st.permutations(list(range(8))))
def test_insertion_order_never_matters(order):
    acts = [act(day=i % 3, entity=f"e{i}", payload={"n": i}) for i in range(8)]
    a, b = Scheduler(), Scheduler()
    for i in order:
        a.push(acts[i])
    for i in range(8):
        b.push(acts[i])
    assert [a.pop() for _ in acts] == [b.pop() for _ in acts]


def test_payload_breaks_remaining_ties():
    s = Scheduler()
    s.push(act(payload={"n": 2}))
    s.push(act(payload={"n": 1}))
    first, second = s.pop(), s.pop()
    assert first.key() < second.key()


def test_identical_activations_are_an_error():
    s = Scheduler()
    s.push(act(payload={"n": 1}))
    with pytest.raises(ValueError):
        s.push(act(payload={"n": 1}))


def test_cannot_schedule_into_the_past():
    s = Scheduler()
    s.push(act(day=5))
    s.pop()
    with pytest.raises(ValueError):
        s.push(act(day=4))
    s.push(act(day=5, entity="e2"))  # same day is fine


def test_peek_and_len():
    s = Scheduler()
    assert s.peek() is None and len(s) == 0
    s.push(act(day=3))
    s.push(act(day=1, entity="e2"))
    assert s.peek().date == Date(1, 1, 1) and len(s) == 2


def test_pop_due_takes_everything_up_to_a_date():
    s = Scheduler()
    for d in (1, 2, 2, 5):
        s.push(act(day=d, entity=f"e{d}{len(s)}"))
    assert [a.date.day for a in s.pop_due(Date(1, 1, 2))] == [1, 2, 2]
    assert len(s) == 1


# ---------------------------------------------------------------- activations


def test_activation_id_is_stable_and_depends_on_everything():
    a = act(payload={"n": 1}, causes=(Cause("event", "x1"),))
    assert a.id == act(payload={"n": 1}, causes=(Cause("event", "x1"),)).id
    assert a.id.startswith("a")
    assert a.id != act(payload={"n": 2}, causes=(Cause("event", "x1"),)).id
    assert a.id != act(payload={"n": 1}, causes=(Cause("event", "x2"),)).id


@pytest.mark.parametrize(
    "bad",
    [
        dict(priority=1.0),
        dict(entity=""),
        dict(purpose=None),
        dict(system=3),
        dict(payload={"s": {1, 2}}),
    ],
)
def test_bad_activations_are_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        act(**bad)


def test_activation_date_must_be_a_date():
    with pytest.raises(TypeError):
        Activation((1, 1, 0), 0, "e1", "p", "s", {}, ())


# ---------------------------------------------------------------- JSON


def test_scheduler_json_round_trips_and_is_sorted():
    s = Scheduler()
    s.push(act(day=3, causes=(Cause("event", "x1"),)))
    s.push(act(day=1, entity="e2", payload={"k": [1, 2]}))
    s.pop()
    j = s.to_json()
    again = Scheduler.from_json(j)
    assert again.to_json() == j
    assert again.pop() == s.pop()


def test_from_json_keeps_the_past_guard():
    s = Scheduler()
    s.push(act(day=5))
    s.pop()
    again = Scheduler.from_json(s.to_json())
    with pytest.raises(ValueError):
        again.push(act(day=4))


# ---------------------------------------------------------------- cadences


@pytest.mark.parametrize(
    "cadence, after",
    [("daily", Date(1, 1, 6)), ("monthly", Date(1, 1, 30)), ("seasonal", Date(1, 1, 90)), ("yearly", Date(1, 2, 0))],
)
def test_next_due(cadence, after):
    assert next_due(CAL, Date(1, 1, 5), cadence) == after


def test_next_due_rejects_unknown_cadences():
    with pytest.raises(ValueError):
        next_due(CAL, Date(1, 1, 5), "fortnightly")


def test_next_due_is_none_at_the_end_of_the_age():
    assert next_due(CAL, Date(1, 300, 200), "yearly") is None
    with pytest.raises(AgeBoundaryError):
        CAL.start_of_next(Date(1, 300, 200), "year")
