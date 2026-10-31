import pytest

from renasci.core.pools import Pool, Pools


class Thing:
    def __init__(self, name):
        self.name = name


def pool(**kw):
    return Pool("things", **kw)


def test_a_pool_is_a_mapping_in_sorted_order_whatever_the_order_added():
    p = pool()
    for name in ("b", "c", "a"):
        p.add(Thing(name))
    assert list(p) == ["a", "b", "c"]
    assert [t.name for t in p.values()] == ["a", "b", "c"]
    assert p["b"].name == "b" and "c" in p and len(p) == 3 and p


def test_adding_a_class_adds_an_instance_and_hands_the_class_back():
    p = pool()

    @p.add
    class Serenade:
        name = "Serenade"

    assert isinstance(p["Serenade"], Serenade)


def test_a_key_can_be_read_from_a_dict():
    p = Pool("verdicts", key=lambda v: v["id"])
    p.add({"id": "exile"})
    assert list(p) == ["exile"]


def test_two_entries_with_one_key_are_refused():
    p = pool()
    p.add(Thing("a"))
    with pytest.raises(ValueError, match="things.*'a'"):
        p.add(Thing("a"))


def test_an_entry_with_no_key_is_refused():
    with pytest.raises(ValueError, match="no key"):
        pool().add(Thing(""))


def test_a_frozen_pool_refuses_additions():
    p = pool()
    p.add(Thing("a"))
    p.freeze()
    with pytest.raises(ValueError, match="frozen"):
        p.add(Thing("b"))
    assert list(p) == ["a"]


def test_an_unknown_key_names_the_pool():
    with pytest.raises(KeyError, match="things"):
        pool()["nope"]


def test_a_copy_is_open_and_separate_from_its_source():
    p = pool()
    p.add(Thing("a"))
    p.freeze()
    q = p.copy()
    q.add(Thing("b"))
    assert list(q) == ["a", "b"] and list(p) == ["a"]


def test_the_registry_holds_every_pool_by_name():
    all_ = Pools()
    things = all_.define("things")
    assert all_.things is things and all_["things"] is things and list(all_) == ["things"]
    with pytest.raises(ValueError, match="things"):
        all_.define("things")
    with pytest.raises(AttributeError, match="nope"):
        all_.nope


def test_the_registry_describes_its_contents_with_their_source():
    all_ = Pools()
    all_.define("things").add(Thing("a"))
    all_.things.add(Thing("b"), source="my_beats")
    assert all_.describe() == {"things": {"a": "base", "b": "my_beats"}}


def test_a_snapshot_copies_every_pool():
    all_ = Pools()
    all_.define("things").add(Thing("a"))
    snap = all_.snapshot()
    snap.things.add(Thing("b"))
    assert list(all_.things) == ["a"] and list(snap.things) == ["a", "b"]


def test_actions_and_ambitions_are_pools_on_the_one_registry():
    from renasci.core.pools import pools
    from renasci.people import actions, ambitions

    assert pools.actions is actions.ACTIONS and pools.ambitions is ambitions.LIBRARY
    assert pools.actions.frozen and pools.ambitions.frozen
    assert list(pools.ambitions) == sorted(pools.ambitions)
