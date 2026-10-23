"""Belief shares among the masses (S6 spec §9, #88)."""

import sys

from hypothesis import given
from hypothesis import strategies as st
from pathlib import Path

from renasci.core.calendar import Span
from renasci.people import beliefs as B

sys.path.insert(0, str(Path(__file__).parent))
from test_telling import run_gossip  # noqa: E402


def test_shares_follow_the_notables_mean_toward_it_a_step_a_season():
    c = B.claim("killed", victim="p:1", by="p:2")
    people = {"a": {B.key(c): {"claim": c, "conf": 0.8}}, "b": {B.key(c): {"claim": c, "conf": 0.4}}, "c": {}}
    after = B.shares_step({}, people)
    assert after[B.key(c)]["share"] == round(B.MASSES_FOLLOW * 0.4, 4)  # mean 0.4 over three notables
    again = B.shares_step(after, people)
    assert after[B.key(c)]["share"] < again[B.key(c)]["share"] < 0.4


def test_shares_in_a_topic_never_sum_past_one_and_stay_in_bounds():
    c, d = B.claim("killed", victim="p:1", by="p:2"), B.claim("killed", victim="p:1", by="p:3")
    shares = {B.key(c): {"claim": c, "share": 0.9}, B.key(d): {"claim": d, "share": 0.9}}
    people = {"a": {B.key(c): {"claim": c, "conf": 1.0}, B.key(d): {"claim": d, "conf": 1.0}}}
    after = B.shares_step(shares, people)
    assert sum(x["share"] for x in after.values()) <= 1.0 + 1e-9
    assert all(0 <= x["share"] <= 1 for x in after.values())


def test_a_claim_nobody_holds_fades_from_the_masses_and_is_dropped():
    c = B.claim("killed", victim="p:1", by="p:2")
    shares = {B.key(c): {"claim": c, "share": 0.012}}  # (a quarter of the way to 0: under the floor)
    assert B.shares_step(shares, {"a": {}}) == {}


def test_shares_are_capped_by_size():
    people = {"a": {B.key(c): {"claim": c, "conf": 0.5}
                    for c in (B.claim("killed", victim=f"p:{i}", by="p:x") for i in range(B.SHARE_CAP + 6))}}
    assert len(B.shares_step({}, people)) == B.SHARE_CAP


def test_settlements_carry_shares_in_a_run():
    e = run_gossip(years=3)
    with_shares = [s for s in e.store.ids("settlement") if e.store.get(s, "shares")]
    assert with_shares
    for s in with_shares:
        sh = e.store.get(s, "shares")
        assert all(0 < x["share"] <= 1 for x in sh.values())
    assert any(ev.type == "belief.shares" for ev in e.events)


@given(st.lists(st.floats(0, 1), min_size=1, max_size=6), st.lists(st.floats(0, 1), min_size=1, max_size=6))
def test_no_topic_ever_sums_past_one(olds, confs):
    claims = [B.claim("killed", victim="p:1", by=f"p:{i}") for i in range(max(len(olds), len(confs)))]
    shares = {B.key(c): {"claim": c, "share": round(s, 4)} for c, s in zip(claims, olds)}
    people = {f"n{i}": {B.key(c): {"claim": c, "conf": conf}} for i, (c, conf) in enumerate(zip(claims, confs))}
    after = B.shares_step(shares, people)
    assert sum(x["share"] for x in after.values()) <= 1.0
    assert all(0 <= x["share"] <= 1 for x in after.values())


def test_a_claim_a_few_hold_takes_hold_among_the_masses():
    c = B.claim("killed", victim="p:1", by="p:2")
    people = {f"n{i}": {} for i in range(19)} | {"believer": {B.key(c): {"claim": c, "conf": 0.6}}}  # target 0.03
    shares = {}
    for _ in range(40):
        shares = B.shares_step(shares, people)
    assert 0.02 < shares[B.key(c)]["share"] <= 0.03


def test_small_moves_are_not_worth_a_write():
    c = B.claim("killed", victim="p:1", by="p:2")
    before = {B.key(c): {"claim": c, "share": 0.4}}
    assert not B.shares_changed(before, {B.key(c): {"claim": c, "share": 0.403}})
    assert B.shares_changed(before, {B.key(c): {"claim": c, "share": 0.41}})
    assert B.shares_changed(before, {})
