"""A scenario's geography in a run, and the Pyrosia draft (S4 spec §2-3, §7, #76)."""

import copy
import json
from pathlib import Path

import pytest

from renasci import geo, renascita

REAL = Path(__file__).parents[2] / "docs"


def small_geography(sc):
    """Every settlement of `sc` in its region, in a line of 3-day roads."""
    regions = sorted({s["region"] for s in sc["settlements"]})
    ids = [s["id"] for s in sc["settlements"]]
    return {"regions": [{"id": r} for r in regions],
            "places": [{"id": s["id"], "kind": "settlement", "region": s["region"]} for s in sc["settlements"]]
                      + [{"id": "g:ruin", "kind": "ruin", "region": regions[0]}],
            "routes": [{"id": f"g:r{i}", "ends": [a, b], "days": 3, "kind": "road"}
                       for i, (a, b) in enumerate(zip(ids, ids[1:] + ["g:ruin"]))]}


def bare():
    sc = copy.deepcopy(renascita.SCENARIO)
    sc.pop("geography", None)
    return sc


def test_synthesis_casts_the_scenarios_geography():
    sc = bare()
    sc["geography"] = small_geography(sc)
    e = renascita.new_engine(scenario=sc)
    assert len(e.store.ids("route")) == len(sc["settlements"])
    assert e.store.ids("place") == ["g:ruin"] and e.store.get("g:r0", "days") == 3


def test_a_scenario_whose_settlements_disagree_with_its_geography_does_not_run():
    sc = bare()
    g = small_geography(sc)
    g["places"] = [p for p in g["places"] if p["id"] != sc["settlements"][-1]["id"]]
    g["routes"] = [r for r in g["routes"] if sc["settlements"][-1]["id"] not in r["ends"]]
    sc["geography"] = g
    with pytest.raises(ValueError, match="settlements_differ"):
        renascita.new_engine(scenario=sc)


def test_a_scenario_without_geography_casts_none():
    e = renascita.new_engine(scenario=bare())
    assert e.store.ids("route") == [] and e.store.ids("region") == []


def test_attach_reads_a_named_geography_next_to_the_scenario(tmp_path):
    sc = bare()
    geo.save(tmp_path / "world.json", small_geography(sc))
    sc["geography"] = "world.json"
    assert geo.attach(sc, tmp_path)["geography"]["routes"][0]["id"] == "g:r0"


def test_the_fourth_age_names_the_pyrosia_draft_and_every_settlement_is_connected():
    g = renascita.SCENARIO["geography"]
    assert isinstance(g, dict) and g.get("draft") is True
    assert [f for f in geo.check(g)] == []  # no errors, and not even the disconnected warning
    assert geo.check_scenario(renascita.SCENARIO, g) == []
    assert 20 <= len(g["places"]) <= 40
    assert not any("at" in p for p in g["places"])  # no positions from the private map (S4 §7)


def test_the_draft_file_is_saved_in_the_canonical_layout():
    p = Path(renascita.__file__).parent / "pyrosia.json"
    assert p.read_text(encoding="utf-8").replace("\r\n", "\n") == geo.dumps(geo.load(p))


@pytest.mark.skipif(not REAL.is_dir(), reason="no vault in this checkout")
def test_every_vault_id_in_the_draft_is_one_the_vault_would_give():
    from renasci.vault.ids import assign
    from renasci.vault.loader import load

    given = set(assign(load(REAL)).values())
    g = renascita.SCENARIO["geography"]
    ours = [x["id"] for x in g["places"] + g["regions"] if x["id"].startswith("v:")]
    assert ours and [i for i in ours if i not in given] == []


def test_a_run_folder_keeps_the_geography_it_ran_with(tmp_path):
    from renasci.cli import main

    recipe = tmp_path / "geo.toml"
    recipe.write_text('[run]\nname = "geo"\nengine = "0.1.0"\nseed = 1\nworld = "fourth_age"\nend = "4A 2"\n',
                      encoding="utf-8")
    assert main(["run", str(recipe), "--out", str(tmp_path / "runs")]) == 0
    kept = json.loads((tmp_path / "runs" / "geo" / "geography.json").read_text(encoding="utf-8"))
    assert kept == renascita.SCENARIO["geography"]


def test_a_place_missing_a_field_is_reported_not_a_crash():
    sc = bare()
    g = small_geography(sc)
    del g["places"][0]["kind"]
    sc["geography"] = g
    with pytest.raises(ValueError, match="missing_field"):
        renascita.new_engine(scenario=sc)


def test_a_scenario_override_may_name_the_geography_file():
    sc = bare()
    sc["geography"] = "pyrosia.json"
    e = renascita.new_engine(scenario=sc)
    assert len(e.store.ids("route")) == len(renascita.SCENARIO["geography"]["routes"])


def test_the_scenario_generator_keeps_the_geography_and_the_traits():
    root = Path(__file__).parents[2]
    src = (root / "scripts" / "fourth_age_draft.py").read_text(encoding="utf-8")
    assert '"geography": "pyrosia.json"' in src and '"traits"' in src
