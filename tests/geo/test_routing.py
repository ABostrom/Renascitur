"""Routing by mode, season, time of day and access (S4 spec §8, #78).

A route's `days` are days on foot in fair weather, walking by day. A traveller's mode scales each kind of
route (or can't take it), the season slows or closes some kinds, the Vialux is lit so a day's walk goes on
past dusk, and a route can be barred to travellers who carry a mark (the Stained).
"""

import pytest

from renasci import geo
from renasci.geo import Travel

ROUTES = [
    {"id": "g:a-b", "ends": ["t:a", "t:b"], "days": 10, "kind": "road"},
    {"id": "g:b-c", "ends": ["t:b", "t:c"], "days": 10, "kind": "road", "vialux": True},
    {"id": "g:a-c", "ends": ["t:a", "t:c"], "days": 12, "kind": "pass"},
    {"id": "g:c-d", "ends": ["t:c", "t:d"], "days": 4, "kind": "sea"},
    {"id": "g:a-d", "ends": ["t:a", "t:d"], "days": 30, "kind": "track", "barred": ["stained"]},
]
TABLE = geo.routing_table(True)
FOOT = Travel("foot", "Summer")


def test_without_a_traveller_routing_is_as_before():
    assert geo.shortest(ROUTES, "t:a", "t:c") == (12, ["t:a", "t:c"])


def test_on_foot_in_summer_the_days_are_the_files():
    assert geo.shortest(ROUTES, "t:a", "t:c", FOOT, TABLE) == (12, ["t:a", "t:c"])


def test_a_rider_is_faster_on_roads_than_over_a_pass():
    days, path = geo.shortest(ROUTES, "t:a", "t:c", Travel("horse", "Summer"), TABLE)
    assert path == ["t:a", "t:b", "t:c"] and days < 12  # (half the road, and the lit Vialux faster still)


def test_a_cart_cannot_take_a_pass():
    assert geo.shortest([ROUTES[2]], "t:a", "t:c", Travel("cart", "Summer"), TABLE) is None


def test_a_pass_closes_in_winter_and_the_road_is_taken_instead():
    days, path = geo.shortest(ROUTES, "t:a", "t:c", Travel("foot", "Winter"), TABLE)
    assert path == ["t:a", "t:b", "t:c"]


def test_the_vialux_is_walked_into_the_night():
    lit = geo.shortest([ROUTES[1]], "t:b", "t:c", FOOT, TABLE)[0]
    dark = geo.shortest([{**ROUTES[1], "vialux": False}], "t:b", "t:c", FOOT, TABLE)[0]
    assert lit < dark == 10


def test_anyone_can_take_passage_by_sea():
    for mode in ("foot", "horse", "cart", "army"):
        assert geo.shortest([ROUTES[3]], "t:c", "t:d", Travel(mode, "Summer"), TABLE) is not None


def test_a_route_barred_to_the_stained_is_closed_to_them_only():
    track = [ROUTES[4]]
    assert geo.shortest(track, "t:a", "t:d", FOOT, TABLE) == (30, ["t:a", "t:d"])
    assert geo.shortest(track, "t:a", "t:d", Travel("foot", "Summer", frozenset({"stained"})), TABLE) is None


def test_part_days_round_up_and_reach_uses_the_same_costs():
    days = geo.shortest([ROUTES[0]], "t:a", "t:b", Travel("horse", "Winter"), TABLE)[0]
    assert days == 6  # (10 days x 0.5 for a horse x 1.2 for a winter road)
    assert geo.within(ROUTES, "t:a", 6, Travel("horse", "Winter"), TABLE).get("t:b") == 6


def test_a_world_can_override_the_table():
    t = geo.routing_table({"modes": {"horse": {"road": 0.25}}})
    assert geo.shortest([ROUTES[0]], "t:a", "t:b", Travel("horse", "Summer"), t)[0] == 3
    assert t["modes"]["foot"] == TABLE["modes"]["foot"]  # (the rest stays the default)


def test_part_days_add_up_before_rounding():
    legs = [{"id": f"g:{i}", "ends": [f"t:{i}", f"t:{i + 1}"], "days": 1, "kind": "road"} for i in range(3)]
    assert geo.shortest(legs, "t:0", "t:3", Travel("horse", "Summer"), TABLE)[0] == 2  # (1.5, not 3 x 1)
    assert geo.within(legs, "t:0", 2, Travel("horse", "Summer"), TABLE)["t:3"] == 2


def test_a_journey_takes_at_least_a_day():
    t = geo.routing_table({"modes": {"horse": {"road": 1e-12}}})
    assert geo.shortest([ROUTES[0]], "t:a", "t:b", Travel("horse", "Summer"), t)[0] == 1


def test_in_a_mode_null_means_it_cant_take_that_kind():
    t = geo.routing_table({"modes": {"cart": {"track": None}}})
    assert "track" not in t["modes"]["cart"]
    assert geo.shortest([ROUTES[4]], "t:a", "t:d", Travel("cart", "Summer"), t) is None


def test_an_empty_table_is_the_defaults():
    assert geo.routing_table({}) == TABLE


@pytest.mark.parametrize("bad", [{"modes": {"horse": {"road": 0}}}, {"vialux": 2}, {"seasons": {"pass": {"Winter": -1}}},
                                 {"default_mode": "griffin"}, {"nonsense": 1}, "yes", {"modes": {"horse": None}},
                                 {"seasons": {"pass": None}}, {"modes": [1]}, {"default_mode": ["x"]},
                                 {"water": {"road": 0.1}}, {"water": {"lake": 1}}, {"seasons": {"bog": {"Winter": 2}}},
                                 {"modes": {"horse": {"sea": 0.5}}}])
def test_a_bad_table_is_refused(bad):
    with pytest.raises(ValueError):
        geo.routing_table(bad)


def test_barred_must_be_a_list_of_marks():
    doc = {"regions": [{"id": "g:r"}], "places": [{"id": "t:a", "kind": "settlement", "region": "g:r"},
                                                   {"id": "t:b", "kind": "settlement", "region": "g:r"}],
           "routes": [{"id": "g:a-b", "ends": ["t:a", "t:b"], "days": 1, "kind": "road", "barred": "stained"}]}
    assert any(f["kind"] == "bad_barred" for f in geo.check(doc))
