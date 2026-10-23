"""Latch points (S7 spec §8, #96): moments a small change would have mattered, ranked, each a ready what-if."""

import json

import pytest

from renasci.cli import main
from renasci.io.recipe import parse_recipe

RECIPE = """
[run]
name = "kin-base"
engine = "0.1.0"
seed = 1234
world = "kin"
end = "1K 40"
checkpoint_every_years = 5
"""


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("latch")
    recipe = tmp / "kin-base.toml"
    recipe.write_text(RECIPE, encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(tmp / "runs")]) == 0
    assert main(["latch", str(tmp / "runs" / "kin-base"), "--top", "5"]) == 0
    return tmp / "runs" / "kin-base"


def points(run):
    return json.loads((run / "analysis" / "latch.json").read_text(encoding="utf-8"))["points"]


def test_latch_points_are_ranked_and_each_suggests_a_ripple(run):
    ps = points(run)
    assert ps and [p["rank"] for p in ps] == list(range(1, len(ps) + 1))
    assert all(a["score"] >= b["score"] for a, b in zip(ps, ps[1:]))
    assert {"died_unfulfilled", "near_miss"} <= {p["kind"] for p in ps}
    for p in ps:
        r = p["ripple"]
        assert r["kind"] in ("protect", "doom") and r["target"] == p["person"] and p["means"] and p["why"]
        if p["kind"] == "died_unfulfilled":
            assert r["kind"] == "protect" and p["ambitions"]
        else:
            assert r["kind"] == "doom" and 0 <= p["margin"]


def test_latch_points_are_deterministic(run):
    first = (run / "analysis" / "latch.json").read_text(encoding="utf-8")
    assert main(["latch", str(run)]) == 0
    assert (run / "analysis" / "latch.json").read_text(encoding="utf-8") == first


@pytest.mark.parametrize("kind", ["died_unfulfilled", "near_miss"])
def test_the_top_latch_point_of_each_kind_replays_and_diffs_cleanly(run, kind):
    n = next(p["rank"] for p in points(run) if p["kind"] == kind)
    out = run.parent
    assert main(["latch", str(run), "--launch", str(n), "--out", str(out)]) == 0
    variant = out / f"kin-base-latch{n}"
    recipe = load_recipe_from(variant)
    assert [r.id for r in recipe.ripples] == [f"latch{n}"]
    report = json.loads((variant / "analysis" / "divergence.json").read_text(encoding="utf-8"))
    assert report["divergent_events"] > 0
    assert report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0


def load_recipe_from(folder):
    """The recipe a run folder was made from (kept, parsed, in its manifest)."""
    return parse_recipe(json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["meta"]["recipe"])


def test_each_kind_leads_on_its_own_scale(run):
    """Scores are normalised per kind, so the listing's top shows one of each, not ten near misses."""
    ps = points(run)
    assert {ps[0]["kind"], ps[1]["kind"]} == {"died_unfulfilled", "near_miss"}
    assert ps[0]["score"] == ps[1]["score"] == 1.0 and all(p["potential"] > 0 for p in ps)


def test_a_doom_on_someone_protected_is_foiled_not_a_crash():
    from renasci.core.calendar import Date
    from renasci.core.ripples import Ripple
    from renasci.kin import new_engine

    probe = new_engine()
    target = probe.store.get(probe.store.ids("settlement")[0], "residents")[0]
    e = new_engine(ripples=[Ripple("p", "protect", Date(1, 3, 0), target, {"until": [1, 9, 359]}),
                            Ripple("d", "doom", Date(1, 4, 0), target)])
    e.run(until=Date(1, 5, 0))
    assert e.store.status(target) == "active"
    assert any(ev.type == "people.near_miss" and ev.roles["survivor"] == (target,) for ev in e.events)
