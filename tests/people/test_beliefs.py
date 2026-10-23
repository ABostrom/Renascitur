"""Claims, beliefs and perception (S6 spec §2-5, #86), and offline truth (§3)."""

import copy

import pytest

from renasci import renascita
from renasci.analysis import truth
from renasci.core.calendar import Span
from renasci.core.engine import Engine
from renasci.core.systems import Ruleset, System
from renasci.people import actions as A
from renasci.people import beliefs as B
from renasci.people import life
from renasci.people.scenario import synthesise
from renasci.people.world import people_ruleset

START, CAL = renascita.START, renascita.CAL


# ---------------------------------------------------------------- claims (values, keys, topics)


def test_a_claim_is_a_canonical_value_with_a_stable_key():
    a = B.claim("killed", victim="p:1", by="p:2")
    assert a == {"pred": "killed", "args": {"by": "p:2", "victim": "p:1"}}
    assert B.key(a) == B.key(B.claim("killed", by="p:2", victim="p:1")) and B.key(a).startswith("c:")
    assert B.key(a) != B.key(B.claim("killed", victim="p:1", by="p:3"))
    with pytest.raises(ValueError):
        B.claim("nonsense", x="y")
    with pytest.raises(ValueError):
        B.claim("killed", victim="p:1")  # (an argument missing)


def test_claims_about_the_same_question_share_a_topic():
    death = "x9"
    assert B.topic(B.claim("killed", victim="p:1", by="p:2")) == B.topic(B.claim("killed", victim="p:1", by="illness"))
    assert B.topic(B.claim("killed", victim="p:1", by="p:2")) != B.topic(B.claim("killed", victim="p:9", by="p:2"))
    assert B.topic(B.claim("caused", event=death, by="v:house-a")) == B.topic(B.claim("fault", event=death, party="guild"))


# ---------------------------------------------------------------- a world with beliefs, and a probe

SEEN: dict = {}
PLAN: dict = {}


class Probe(System):
    name, cadence, priority = "toy.probe", "yearly", 99
    reads = B.PERCEIVE_READS | A.READS | life.DIE_READS | frozenset({"ids:settlement", "ids:person", "residents", "place", "status", "house"}).union(
        *(a.reads for a in A.ACTIONS.values()))
    writes = B.PERCEIVE_WRITES | A.WRITES | life.DIE_WRITES
    event_types = tuple({t.name: t for t in B.EVENT_TYPES + A.EVENT_TYPES + life.DIE_EVENTS}.values())

    def run(self, ctx):
        if ctx.today == START:
            for i, (after, _) in enumerate(PLAN["steps"]):
                ctx.schedule(after, "probe", entity="t:probe", payload={"i": i})

    def handle(self, ctx, activation):
        PLAN["steps"][activation.payload["i"]][1](ctx)


def scenario(beliefs=True):
    sc = copy.deepcopy(renascita.SCENARIO)
    sc.pop("geography", None)
    sc["params"] = {**sc["params"], **({"beliefs": True} if beliefs else {})}
    return sc


def engine(steps, sc=None, seed=5):
    PLAN["steps"] = steps
    SEEN.clear()
    sc = sc or scenario()
    rs = people_ruleset("fourth_age", sc)
    rs = Ruleset(rs.name, rs.version, rs.systems + (Probe(),), params=rs.params, forcers=rs.forcers,
                 disguises=rs.disguises, conservation=rs.conservation)
    e = Engine(CAL, seed=seed, rulesets=[(START, rs)])
    synthesise(e, sc, seed)
    return e


def two_adults(ctx):
    home = renascita.SCENARIO["settlements"][0]["id"]
    people = [p for p in ctx.get(home, "residents") if A._adult(ctx, p)]
    return home, people[0], people[1], people


def emit_probe_event(ctx, actor, secret=False):
    return ctx.emit("people.action", {"actor": (actor,)}, purpose="probe", actor=actor,
                    payload={"action": "Probe", "outcome": "success"}, visibility="secret" if secret else None)


# ---------------------------------------------------------------- holding beliefs


def test_holding_a_belief_halves_its_rivals_and_reinforcing_is_silent():
    def go(ctx):
        _, a, b, _ = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        truth_ = B.claim("killed", victim=b, by=a)
        cover = B.claim("killed", victim=b, by="a wasting illness")
        SEEN["first"] = B.hold(ctx, a, cover, 0.6, ev.id)
        SEEN["second"] = B.hold(ctx, a, truth_, 0.8, ev.id)
        SEEN["again"] = B.hold(ctx, a, truth_, 0.5, ev.id)  # weaker than held: reinforcement, no change
        SEEN["beliefs"] = ctx.get(a, "beliefs")
        SEEN["keys"] = (B.key(truth_), B.key(cover))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    t, c = SEEN["keys"]
    assert SEEN["first"] and SEEN["second"] and not SEEN["again"]
    assert SEEN["beliefs"][t]["conf"] == 0.8 and SEEN["beliefs"][c]["conf"] == 0.3
    assert SEEN["beliefs"][t]["claim"]["pred"] == "killed"


def test_beliefs_are_capped_by_salience_and_confidence():
    def go(ctx):
        _, a, b, people = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        for i, p in enumerate(people[: B.BELIEF_CAP + 5]):
            B.hold(ctx, a, B.claim("killed", victim=p, by=b), 0.2 + i * 0.01, ev.id)
        SEEN["n"] = len(ctx.get(a, "beliefs"))
        SEEN["min"] = min(x["conf"] for x in ctx.get(a, "beliefs").values())

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["n"] == B.BELIEF_CAP and SEEN["min"] > 0.2


# ---------------------------------------------------------------- perceiving


def test_participants_and_a_few_bystanders_perceive_a_public_event():
    def go(ctx):
        home, a, b, _ = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        c = B.claim("killed", victim=b, by=a)
        SEEN["who"] = B.perceive(ctx, ev.id, home, participants=[a], claim=c)
        SEEN["a"] = ctx.get(a, "beliefs")[B.key(c)]["conf"]
        SEEN["home"], SEEN["a_id"] = home, a

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["a"] == B.PARTICIPANT_CONF
    bystanders = [w for w in SEEN["who"] if w != SEEN["a_id"]]
    assert 1 <= len(bystanders) <= B.WITNESS_CAP
    perceived = [ev for ev in e.events if ev.type == "belief.perceived"]
    assert len(perceived) == len(SEEN["who"]) and all(any(c.kind == "event" for c in ev.causes) for ev in perceived)


def test_a_secret_event_is_perceived_by_its_participants_only():
    def go(ctx):
        home, a, b, _ = two_adults(ctx)
        ev = emit_probe_event(ctx, a, secret=True)
        SEEN["who"] = B.perceive(ctx, ev.id, home, participants=[a], claim=B.claim("killed", victim=b, by=a),
                                 secret=True)
        SEEN["a"] = a

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN["who"] == [SEEN["a"]]


def test_a_poisoning_shows_the_public_its_cover_and_the_poisoner_the_truth():
    def go(ctx):
        home, a, b, _ = two_adults(ctx)
        SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Poison"], a, b, odds=1.0)
        SEEN.update(a=a, b=b, home=home)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    if SEEN["outcome"] == "exposed":
        pytest.skip("this seed exposed the poisoning before it happened")
    a, b = SEEN["a"], SEEN["b"]
    truth_key, cover_key = B.key(B.claim("killed", victim=b, by=a)), B.key(B.claim("killed", victim=b, by="a wasting illness"))
    believers = {eid: e.store.get(eid, "beliefs") or {} for eid in e.store.ids("person")}
    assert truth_key in believers[a]
    knows_truth = [p for p, bs in believers.items() if truth_key in bs]
    saw_cover = [p for p, bs in believers.items() if cover_key in bs]
    assert knows_truth == [a] and saw_cover and a not in saw_cover


def test_an_open_killing_is_seen_as_what_it_was():
    def go(ctx):
        home, a, b, _ = two_adults(ctx)
        life.die(ctx, b, home, "fell in a duel", killer=a)
        SEEN.update(a=a, b=b)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    k = B.key(B.claim("killed", victim=SEEN["b"], by=SEEN["a"]))
    assert k in (e.store.get(SEEN["a"], "beliefs") or {})


def test_without_the_beliefs_param_nobody_perceives_anything():
    def go(ctx):
        home, a, b, _ = two_adults(ctx)
        life.die(ctx, b, home, "fell in a duel", killer=a)

    e = engine([(Span(days=1), go)], sc=scenario(beliefs=False))
    e.run(until=CAL.add(START, Span(days=3)))
    assert not any(ev.type.startswith("belief.") for ev in e.events)
    assert all(not e.store.get(p, "beliefs") for p in e.store.ids("person"))


# ---------------------------------------------------------------- offline truth


EVENTS = [
    {"id": "xact", "type": "people.action", "roles": {"actor": ["p:a"], "target": ["p:b"]}, "causes": [],
     "payload": {"action": "Poison", "outcome": "success"}, "visibility": "secret"},
    {"id": "xdeath", "type": "people.death", "roles": {"deceased": ["p:b"]}, "causes": [["event", "xact"]],
     "payload": {"cause": "a wasting illness"}},
    {"id": "xduel", "type": "people.death", "roles": {"deceased": ["p:c"], "killer": ["p:a"]}, "causes": [],
     "payload": {"cause": "fell in a duel"}},
    {"id": "xfail", "type": "ward_failure", "roles": {"leader": ["p:c"]}, "causes": [["event", "xsab"]], "payload": {}},
    {"id": "xsab", "type": "sabotage", "roles": {"ordered_by": ["v:vane"]}, "causes": [], "payload": {}},
]


@pytest.mark.parametrize("c, expected", [
    (B.claim("killed", victim="p:b", by="p:a"), "true"),  # through the secret action behind the death
    (B.claim("killed", victim="p:b", by="a wasting illness"), "false"),  # the cover
    (B.claim("killed", victim="p:c", by="p:a"), "true"),
    (B.claim("killed", victim="p:c", by="p:b"), "false"),
    (B.claim("killed", victim="p:zz", by="p:a"), "unknown"),  # nobody died
    (B.claim("caused", event="xfail", by="v:vane"), "true"),  # an ancestor event's participant
    (B.claim("caused", event="xfail", by="guild"), "false"),
    (B.claim("fault", event="xfail", party="ward-keeper"), "false"),
    (B.claim("fault", event="xnope", party="anyone"), "unknown"),
])
def test_truth_is_judged_against_the_event_log(c, expected):
    verdict, basis = truth.judge(c, EVENTS)
    assert verdict == expected
    assert (basis == []) == (expected == "unknown")


# ---------------------------------------------------------------- review regressions


REVENGE = [  # A poisons B; B's son C kills D in a duel for it; a Court succeeded somewhere along the way
    {"id": "xp", "type": "people.action", "roles": {"actor": ["p:A"], "target": ["p:B"]}, "causes": [],
     "payload": {"action": "Poison", "outcome": "success"}},
    {"id": "xdb", "type": "people.death", "roles": {"deceased": ["p:B"]}, "causes": [["event", "xp"]],
     "payload": {"cause": "a wasting illness"}},
    {"id": "xcourt", "type": "people.action", "roles": {"actor": ["p:E"]}, "causes": [["event", "xdb"]],
     "payload": {"action": "Court", "outcome": "success"}},
    {"id": "xduel", "type": "people.action", "roles": {"actor": ["p:C"], "target": ["p:D"]},
     "causes": [["event", "xdb"], ["event", "xcourt"]], "payload": {"action": "Duel", "outcome": "success"}},
    {"id": "xdd", "type": "people.death", "roles": {"deceased": ["p:D"], "killer": ["p:C"]},
     "causes": [["event", "xduel"]], "payload": {"cause": "fell in a duel"}},
]


def test_a_killer_is_only_whoever_struck_the_victim_not_everyone_upstream():
    assert truth.judge(B.claim("killed", victim="p:D", by="p:A"), REVENGE)[0] == "false"
    assert truth.judge(B.claim("killed", victim="p:D", by="p:E"), REVENGE)[0] == "false"
    assert truth.judge(B.claim("killed", victim="p:D", by="p:C"), REVENGE)[0] == "true"
    assert truth.judge(B.claim("killed", victim="p:B", by="p:A"), REVENGE)[0] == "true"


def test_a_victim_never_caused_their_own_misfortune():
    assert truth.judge(B.claim("caused", event="xdd", by="p:D"), REVENGE)[0] == "false"
    assert truth.judge(B.claim("caused", event="xdd", by="p:B"), REVENGE)[0] == "false"
    assert truth.judge(B.claim("caused", event="xdd", by="p:C"), REVENGE)[0] == "true"


def test_a_weaker_claim_does_not_shake_a_firmer_belief_in_its_topic():
    def go(ctx):
        _, a, b, _ = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        truth_, cover = B.claim("killed", victim=b, by=a), B.claim("killed", victim=b, by="a wasting illness")
        B.hold(ctx, a, truth_, 0.8, ev.id)
        SEEN["took"] = B.hold(ctx, a, cover, 0.5, ev.id)
        SEEN["beliefs"], SEEN["keys"] = ctx.get(a, "beliefs"), (B.key(truth_), B.key(cover))

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    t, c = SEEN["keys"]
    assert SEEN["took"] is False and SEEN["beliefs"][t]["conf"] == 0.8 and c not in SEEN["beliefs"]


def test_a_secret_killer_never_takes_on_the_cover_and_knowing_the_truth_stays_secret():
    def go(ctx):
        home, a, b, _ = two_adults(ctx)
        SEEN["outcome"] = A.perform(ctx, A.ACTIONS["Poison"], a, b, odds=1.0)
        SEEN.update(a=a, b=b)

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    if SEEN["outcome"] != "success":
        pytest.skip("this seed didn't poison")
    a = SEEN["a"]
    mine = [ev for ev in e.events if ev.type == "belief.perceived" and ev.roles["holder"] == (a,)]
    assert len(mine) == 1 and mine[0].payload["claim"]["args"]["by"] == a
    assert mine[0].visibility == "secret"


def test_a_belief_the_cap_would_drop_at_once_is_not_taken_on():
    def go(ctx):
        _, a, b, people = two_adults(ctx)
        ev = emit_probe_event(ctx, a)
        for p in people[: B.BELIEF_CAP]:
            B.hold(ctx, a, B.claim("killed", victim=p, by=b), 0.9, ev.id)
        before = len([x for x in ctx._engine.events if x.type == "belief.perceived"])
        SEEN["took"] = B.hold(ctx, a, B.claim("killed", victim=people[B.BELIEF_CAP], by=b), 0.1, ev.id)
        SEEN["emitted"] = len([x for x in ctx._engine.events if x.type == "belief.perceived"]) - before

    e = engine([(Span(days=1), go)])
    e.run(until=CAL.add(START, Span(days=3)))
    assert SEEN == {"took": False, "emitted": 0}


def test_blaming_the_agents_house_is_half_true():
    houses = {"v:vane": "v:house-vane"}
    assert truth.judge(B.claim("caused", event="xfail", by="v:house-vane"), EVENTS, houses=houses)[0] == "half"
    assert truth.judge(B.claim("caused", event="xfail", by="v:house-vane"), EVENTS)[0] == "false"  # (no houses: can't say)
    assert truth.judge(B.claim("caused", event="xfail", by="v:vane"), EVENTS, houses=houses)[0] == "true"
