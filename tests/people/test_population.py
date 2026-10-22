"""Populations as aggregates, promotion, demotion and conservation (S3 spec §8, #71/#72)."""

import pytest

from renasci.analysis.divergence import analyse
from renasci.core.calendar import Date
from renasci.core.ripples import Ripple
from renasci.kin import CATALOGUE, SETTLEMENTS, new_engine
from renasci.people.genome import origin_of
from renasci.people.population import BAND_COLUMNS, allele_column

END = Date(1, 60, 359)


@pytest.fixture(scope="module")
def world():
    e = new_engine(people_per_settlement=20)
    e.full_reads = True
    yearly = []
    for year in range(1, END.year + 1):
        e.run(until=Date(1, year, 359))
        yearly.append(e.check_conservation())
    e.yearly_problems = yearly
    return e


def aggregate(store, settlement):
    return sum(int(store.read_column(c, [settlement])[0]) for c in BAND_COLUMNS)


def test_the_masses_live_and_die(world):
    store = world.store
    for s in SETTLEMENTS:
        n = aggregate(store, s)
        assert 50 <= n <= 1000  # neither dies out nor explodes in 60 years (cast at 200)
        assert all(int(store.read_column(c, [s])[0]) >= 0 for c in BAND_COLUMNS)


def test_conservation_holds_every_year(world):
    assert all(problems == [] for problems in world.yearly_problems), \
        next(p for p in world.yearly_problems if p)


def test_allele_copies_are_twice_the_count(world):
    store = world.store
    for s in SETTLEMENTS:
        n = aggregate(store, s)
        for locus in CATALOGUE["loci"]:
            copies = sum(int(store.read_column(allele_column(locus["id"], v), [s])[0]) for v in locus["variants"])
            assert copies == 2 * n


def test_commoners_are_promoted_to_marry_notables(world):
    commoner = [ev for ev in world.events if ev.type == "people.marriage" and ev.payload["commoner"]]
    promoted = {ev.roles["individual"][0]: ev for ev in world.events if ev.type == "lod.promote"}
    assert commoner and promoted
    for ev in commoner:
        spouses = [p for p in ev.roles["spouse"] if p in promoted]
        assert spouses
        p = spouses[0]
        genome = world.store.get(p, "genome")
        assert all(origin_of(c).startswith("f:t:") for pair in genome.values() for c in pair)
        assert world.store.get(p, "mother") is None and world.store.get(p, "father") is None


def test_quiet_commoners_fade_back_into_the_masses(world):
    demoted = [ev.roles["individual"][0] for ev in world.events if ev.type == "lod.demote"]
    assert demoted
    residents = {p for s in SETTLEMENTS for p in world.store.get(s, "residents")}
    for p in demoted:
        assert world.store.status(p) == "dormant" and p not in residents
        assert world.store.get(p, "house") is None and not world.store.get(p, "offices")


def test_the_timeseries_logs_each_settlement_each_year(world):
    rows = world.pending()["timeseries"]
    years = {(tuple(r["date"])[1], r["entity"]) for r in rows}
    assert len(years) == len(rows)  # one row per settlement per year
    assert {e for _, e in years} == set(SETTLEMENTS)
    r = rows[-1]
    assert set(r["values"]) >= {"pop", "notables"} and len(r["values"]["pop"]["f"]) == 20


def test_a_protect_ripple_is_still_fully_explained(world):
    death = next(ev for ev in world.events if ev.type == "people.death" and 10 <= ev.date.year <= 30
                 and 20 <= ev.payload["age"] <= 45)
    target = death.roles["deceased"][0]
    variant = new_engine(people_per_settlement=20, ripples=[
        Ripple("r1", "protect", Date(1, death.date.year - 1, 0), target, {"until": [1, 60, 359]})])
    variant.full_reads = True
    variant.run(until=END)
    report = analyse(world.pending(), variant.pending(), world.store.to_json(), variant.store.to_json(),
                     ripples=["r1"])
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0, \
        report["unexplained"]


def test_promotion_then_demotion_restores_the_masses_exactly():
    from renasci.core.engine import Engine
    from renasci.core.lod import EVENT_TYPES as LOD
    from renasci.core.systems import Ruleset, System
    from renasci.kin import CAL, START, ruleset
    from renasci.people.population import demote_person, promote_person
    from renasci.people.ties import TIE_ENDED

    class RoundTrip(System):
        name, cadence = "test.roundtrip", "yearly"
        reads = frozenset(ruleset().systems[0].reads) | frozenset(BAND_COLUMNS) | {"residents", "genome", "born",
                                                                                    "sex", "race", "status",
                                                                                    "ties", "a", "b", "kind"}
        writes = frozenset({"new:person", "residents", "status", "ties", "ended"}) | frozenset(BAND_COLUMNS)
        event_types = LOD + (TIE_ENDED,)

        def run(self, ctx):
            s = SETTLEMENTS[0]
            with ctx.scope(s):
                before = {c: int(ctx.read_column(c, [s])[0]) for c in sorted(_all_columns())}
                p = promote_person(ctx, s, "test", sex="f", ages=(16, 40))
                demote_person(ctx, p, s, reason="test")
                after = {c: int(ctx.read_column(c, [s])[0]) for c in sorted(_all_columns())}
                RoundTrip.result = (before, after)

    def _all_columns():
        return [*BAND_COLUMNS, *(allele_column(lo["id"], v) for lo in CATALOGUE["loci"] for v in lo["variants"])]

    base = ruleset()
    rt = RoundTrip()
    rt.writes = rt.writes | frozenset(c for c in _all_columns()) | {"flow:promoted", "flow:demoted"}
    rt.reads = rt.reads | frozenset(_all_columns()) | {"flow:promoted", "flow:demoted"}
    e = new_engine(people_per_settlement=4)
    e.rulesets = [(START, Ruleset("rt", 1, (rt,), params=base.params))]
    e.run(until=Date(1, 1, 359))
    before, after = RoundTrip.result
    assert before == after and CAL
    assert Engine


# ---------------------------------------------------------------- review fixes


def test_only_adults_fade_back(world):
    from renasci.people.races import Race, age_years
    from renasci.kin import RACES

    race = {r["id"]: Race.from_json(r) for r in RACES}
    for ev in world.events:
        if ev.type == "lod.demote":
            p = ev.roles["individual"][0]
            assert age_years(world.calendar, world.store.get(p, "born"), ev.date) >= race[world.store.get(p, "race")].marriage[0]


def test_old_run_folders_without_a_timeseries_table_still_open_and_fork(tmp_path):
    import shutil

    from renasci.io.runfolder import RunFolder

    rf = RunFolder.create(tmp_path / "old", {"complete": True})
    rf.write("events", [{"id": "x"}])
    rf.close_segment()
    shutil.rmtree(tmp_path / "old" / "timeseries")  # as written before #71
    again = RunFolder.open(tmp_path / "old")
    again.write("timeseries", [{"date": [1, 1, 0]}])
    RunFolder.fork(tmp_path / "old", tmp_path / "child", keep=1, meta={})
