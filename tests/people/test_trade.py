"""Trade (S9 spec §4, #125): each year goods flow between neighbouring towns, from plenty to want, on the goods
ledger; a war between the realms that hold them cuts the flow."""

import pytest

from renasci import renascita
from renasci.core.calendar import Span
from renasci.people import crafts, trade


def test_a_flow_runs_from_plenty_to_want_and_never_empties_the_giver():
    assert trade.flow(100, 10, 0, 10, cap=1000) > 0  # (plenty there, none here)
    assert trade.flow(0, 10, 100, 10, cap=1000) == 0  # (only downhill)
    assert trade.flow(50, 10, 50, 10, cap=1000) == 0  # (level)
    n = trade.flow(100, 10, 0, 10, cap=1000)
    assert n <= 50  # (never past the level they'd share)
    assert trade.flow(100, 10, 0, 10, cap=7) == 7  # (the road and the merchants limit it)


@pytest.fixture(scope="module")
def traded():
    e = renascita.new_engine(seed=5, crafts=True)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=12)))
    return e


def test_goods_move_between_neighbours(traded):
    flows = [x for x in traded.events if x.type == "trade.flow"]
    assert flows
    for x in flows:
        (a,), (b,) = x.roles["from"], x.roles["to"]
        goods = {**x.payload["moved"], **x.payload["back"]}  # (either way along the road)
        assert a != b and goods and all(v > 0 for v in goods.values())


def test_the_ledger_still_balances_with_trade(traded):
    mats = traded.rulesets[0][1].params["crafts"]["materials"]
    for s in traded.store.ids("settlement"):
        for m in mats:
            assert crafts.balance(traded.store, s, m) == 0, (s, m)
    out = sum(int(traded.store.read_column(f"goods:{m}:traded_out", [s])[0]) for s in traded.store.ids("settlement") for m in mats)
    inn = sum(int(traded.store.read_column(f"goods:{m}:traded_in", [s])[0]) for s in traded.store.ids("settlement") for m in mats)
    assert out == inn > 0  # (what leaves one town enters another)


def border_flows(stance):
    """Flows between the Empire's Magnus Rest and the Clans' Ashford (neighbours by road), over 3 years with the
    two realms at `stance` from the start (no war entity: only the stance, which drift never sets to war)."""
    sc = renascita._scenario(None, polities="frontier", crafts=True)
    sc["relations"] = [{**r, "stance": stance, "trust": -0.9} for r in sc["relations"]]
    sc["params"]["campaigns"] = False  # (no war declared to end it)
    e = renascita.new_engine(seed=4, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=3)))
    pair = {"v:magnus-rest", "v:draft-ashford"}
    return [x for x in e.events if x.type == "trade.flow" and {x.roles["from"][0], x.roles["to"][0]} == pair]


def test_no_trade_across_a_war():
    assert border_flows("hostile")  # (bitter, but trading)
    assert not border_flows("war")


def test_a_coarse_step_closes_the_gap_as_its_years_would():
    one = trade.flow(1000, 10, 0, 10, cap=10**6, years=1)
    ten = trade.flow(1000, 10, 0, 10, cap=10**6, years=10)
    assert one < ten <= 500


def test_merchants_take_a_cut_of_what_passes(traded):
    paid = [x for x in traded.events if x.type == "trade.flow" and x.payload["merchants"]]
    assert paid
    values = {m: s["value"] for m, s in traded.rulesets[0][1].params["crafts"]["materials"].items()}
    for x in paid:
        worth = sum(values[m] * n for goods in (x.payload["moved"], x.payload["back"]) for m, n in goods.items())
        assert x.payload["cut"] == round(trade.CUT * worth, 2) > 0
        for m in x.payload["merchants"]:
            assert traded.store.get(m, "job") == "merchant" or traded.store.status(m) != "active"


def test_with_trade_on_realms_grow_trust_from_what_passes_between_them():
    sc = renascita._scenario(None, polities="frontier", crafts=True)
    sc["relations"] = [{**r, "stance": "neutral", "trust": 0.0} for r in sc["relations"]]
    sc["params"]["campaigns"] = False
    sc["params"]["trade"] = True
    e = renascita.new_engine(seed=4, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=4)))
    flows = {x.id for x in e.events if x.type == "trade.flow"}
    drifts = [x for x in e.events if x.type == "polity.drift"]
    moved = [d for d in drifts if {c.ref for c in d.causes if c.kind == "event"} & flows]
    assert moved and all(d.payload["moved"] > 0 for d in moved)  # (trust moved, up, by trade itself)
    assert all(d.payload["moved"] <= 0.03 for d in moved)  # (capped as the old flat pull)
