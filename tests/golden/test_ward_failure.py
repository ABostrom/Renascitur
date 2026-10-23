"""The ward failure, the M2 golden scenario (S6 spec §10, #90; the master spec's demo).

The seeds are pinned: the no-witness outcome held on all seven seeds tried; the spared-leader one on
most (on seed 6 the lie still edges it). Tuning trust, drift or the witness's reach can move them.

With no surviving witness, the guild's lie is what the world believes; with the leader spared, their
testimony corrects it and the truth (or its drift onto the rival's house, half-true) spreads. In both, every
belief about the failure walks back to how it began, and a replay's diff explains every divergence.
"""

import copy
import functools
from collections import Counter

import pytest

from renasci import renascita
from renasci.analysis import truth
from renasci.core.calendar import Span
from renasci.core.ripples import Ripple
from renasci.people import beliefs as B

TOWN = "v:lux-oescus"  # on the Vialux
WHEN = renascita.CAL.add(renascita.START, Span(years=1))
YEARS = 6
ORIGINS = ("belief.perceived", "belief.corrected", "belief.heard")


@functools.cache
def run(seed, spare):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc["params"]["beliefs"] = True
    ward = Ripple("ward", "inject", WHEN, TOWN, {"script": "ward_failure", "spare": spare})
    e = renascita.new_engine(seed=seed, scenario=sc, ripples=[ward])
    e.run(until=renascita.CAL.add(WHEN, Span(years=YEARS)))
    events = [{"id": ev.id, "type": ev.type, "roles": {k: list(v) for k, v in ev.roles.items()},
               "causes": [[c.kind, c.ref] for c in ev.causes], "payload": ev.payload} for ev in e.events]
    houses = {p: e.store.get(p, "house") for p in e.store.ids("person") if e.store.get(p, "house")}
    failure = next(ev for ev in e.events if ev.type == "ward.failure")
    return e, events, houses, failure


def dominant(e, failure, settlement):
    shares = {k: v for k, v in (e.store.get(settlement, "shares") or {}).items()
              if B.topic(v["claim"]) == f"why:{failure.id}"}
    return shares[max(shares, key=lambda k: (shares[k]["share"], k))]["claim"] if shares else None


def believers(e, events, houses, failure):
    out = Counter()
    for p in e.store.ids("person"):
        for b in (e.store.get(p, "beliefs") or {}).values():
            if B.topic(b["claim"]) == f"why:{failure.id}":
                out[truth.judge(b["claim"], events, houses)[0]] += 1
    return out


@pytest.mark.parametrize("seed", [1, 3])
def test_with_no_witness_the_guilds_lie_is_what_the_world_believes(seed):
    e, events, houses, failure = run(seed, spare=None)
    keeper = failure.roles["keeper"][0]
    told = dominant(e, failure, TOWN)
    assert told == B.claim("fault", event=failure.id, party=keeper)  # the lie: the ward-keeper's fault
    along = dominant(e, failure, "v:lions-rest")  # (and along the Vialux)
    assert along is not None and truth.judge(along, events, houses)[0] == "false"
    assert truth.judge(told, events, houses)[0] == "false"
    held = believers(e, events, houses, failure)
    assert held["false"] > held["true"] + held["half"]


@pytest.mark.parametrize("seed", [1, 3])
def test_with_the_leader_spared_the_truth_spreads(seed):
    e, events, houses, failure = run(seed, spare="leader")
    told = dominant(e, failure, TOWN)
    assert truth.judge(told, events, houses)[0] in ("true", "half")
    held = believers(e, events, houses, failure)
    assert held["true"] + held["half"] > held["false"]
    assert any(ev["type"] == "ward.testimony" for ev in events)


@pytest.mark.parametrize("spare", [None, "leader"])
def test_every_belief_about_it_walks_back_to_how_it_began(spare):
    e, events, houses, failure = run(1, spare)
    by_id = {ev["id"]: ev for ev in events}
    walked = 0
    for p in e.store.ids("person"):
        for b in (e.store.get(p, "beliefs") or {}).values():
            if B.topic(b["claim"]) != f"why:{failure.id}":
                continue
            ev = by_id[b["from"]]
            while ev["type"] == "belief.told" and ev["payload"]["intent"] != "lie":
                ev = by_id[next(ref for kind, ref in ev["causes"] if kind == "event")]
            assert ev["type"] in ORIGINS or ev["payload"].get("intent") == "lie", ev["type"]
            walked += 1
    assert walked > 10


def test_a_replay_explains_every_divergent_belief(tmp_path):
    from renasci.cli import main

    body = ('[run]\nname = "{name}"\nengine = "0.1.0"\nseed = 1\nworld = "fourth_age"\nend = "4A 5"\n'
            'checkpoint_every_years = 1\n\n[world]\nscenario = {{ }}\n')
    base = (f'[[ripple]]\nid = "ward"\nkind = "inject"\ndate = "4A 2"\ntarget = "{TOWN}"\n'
            'params = {{ script = "ward_failure"{spare} }}\n')
    sc = copy.deepcopy(renascita.SCENARIO)

    def recipe(name, spare=""):
        text = body.format(name=name).replace("scenario = { }", "scenario = " + _toml_inline(sc, beliefs=True))
        return text + base.format(spare=spare)

    (tmp_path / "base.toml").write_text(recipe("base"), encoding="utf-8")
    (tmp_path / "spared.toml").write_text(recipe("spared", ', spare = "leader"'), encoding="utf-8")
    assert main(["run", str(tmp_path / "base.toml"), "--out", str(tmp_path / "runs")]) == 0
    assert main(["replay", str(tmp_path / "runs" / "base"), "--recipe", str(tmp_path / "spared.toml"),
                 "--out", str(tmp_path / "runs")]) == 0
    assert main(["diff", str(tmp_path / "runs" / "base"), str(tmp_path / "runs" / "spared")]) == 0  # (all explained)


def _toml_inline(value, beliefs=False):
    """A scenario as an inline TOML value (the recipe's [world] scenario)."""
    import json

    if beliefs:
        value = {**value, "params": {**value["params"], "beliefs": True}}
    return _toml(json.loads(json.dumps(value)))


def _toml(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, str):
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if isinstance(v, list):
        return "[" + ", ".join(_toml(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{ " + ", ".join(f'"{k}" = {_toml(x)}' for k, x in v.items()) + " }"
    raise TypeError(type(v))
