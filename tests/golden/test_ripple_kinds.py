"""Every ripple kind, each as a golden (#114; master spec §5.9): a Fourth Age run with beliefs and the
Pyrosia geography, replayed with one ripple of each kind. Each replay does what its kind says, and its
diff against the baseline explains every divergence (the ripple guarantee).

- **favour** `{"by", "until"}`: the target's schemes (draws owned by a scheme or ambition of theirs, or
  by them) succeed more often (`act:` odds up by `by`) and are exposed less often (`expose:` odds down);
- **luck** `{"until"}`: the target's own draws are re-rolled while it lasts (fortune, neither good nor
  bad: which outcome is lucky isn't something the engine knows);
- **plant** `{"claim", "share"}`: a rumour planted in a town's talk (the people world's disguise);
- **structural** `{"route", "open"/"days", "why"}`: the world changes shape (a pass closes), a map change
  made by the people world's disguise.
"""

import copy
import sys
from pathlib import Path

import pytest

from renasci import renascita
from renasci.io.runfolder import RunFolder

sys.path.insert(0, str(Path(__file__).parent))
from test_ward_failure import _toml_inline  # noqa: E402

BODY = ('[run]\nname = "{name}"\nengine = "0.1.0"\nseed = 2\nworld = "fourth_age"\nend = "4A 5"\n'
        'checkpoint_every_years = 1\n\n[world]\nscenario = {scenario}\n')
ROUTE = "g:lions-rest--magnus-rest"
TOWN = "v:lux-oescus"


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    from renasci.cli import main

    root = tmp_path_factory.mktemp("kinds")
    scenario = _toml_inline(copy.deepcopy(renascita.SCENARIO), beliefs=True)
    (root / "base.toml").write_text(BODY.format(name="base", scenario=scenario), encoding="utf-8")
    assert main(["run", str(root / "base.toml"), "--out", str(root / "runs")]) == 0
    return root, scenario


def replay(base, name, kind, date, target, params):
    """Replay the baseline with one ripple; the diff's exit code (0: every divergence explained)."""
    from renasci.cli import main
    from test_ward_failure import _toml

    root, scenario = base
    ripple = (f'[[ripple]]\nid = "{name}"\nkind = "{kind}"\ndate = "{date}"\ntarget = "{target}"\n'
              f'params = {_toml(params)}\n')
    (root / f"{name}.toml").write_text(BODY.format(name=name, scenario=scenario) + ripple, encoding="utf-8")
    assert main(["replay", str(root / "runs" / "base"), "--recipe", str(root / f"{name}.toml"),
                 "--out", str(root / "runs")]) == 0
    return main(["diff", str(root / "runs" / "base"), str(root / "runs" / name)])


def table(base, run, name):
    return list(RunFolder.open(base[0] / "runs" / run).read(name))


def test_favour_makes_a_schemers_steps_likelier_and_every_divergence_is_explained(base):
    begun = next(e for e in table(base, "base", "events") if e["type"] == "people.scheme_begun"
                 and e["date"][1] >= 2)
    owner = begun["roles"]["owner"][0]
    date = f"4A {begun['date'][1]}"
    assert replay(base, "favour", "favour", date, owner, {"by": 0.5, "until": [4, 5, 359]}) == 0
    rows = [r for r in table(base, "favour", "ripples") if r["action"] == "favour"]
    assert rows and all(r["target"] == owner for r in rows)


def test_luck_rerolls_the_targets_draws_and_every_divergence_is_explained(base):
    person = next(e for e in table(base, "base", "events") if e["type"] == "people.scheme_begun")["roles"]["owner"][0]
    assert replay(base, "luck", "luck", "4A 2", person, {"until": [4, 5, 359]}) == 0
    assert any(r["action"] == "luck" for r in table(base, "luck", "ripples"))


def test_plant_puts_a_rumour_in_a_towns_talk(base):
    death = next(e for e in table(base, "base", "events") if e["type"] == "people.death" and e["date"][1] == 1)
    rumour = {"pred": "killed", "args": {"victim": death["roles"]["deceased"][0], "by": "the guild"}}
    assert replay(base, "plant", "plant", "4A 2", TOWN, {"claim": rumour, "share": 0.3}) == 0
    planted = [e for e in table(base, "plant", "events") if e["type"] == "belief.rumour"]
    assert len(planted) == 1 and planted[0]["place"] == TOWN
    talk = next(d for d in table(base, "plant", "state_deltas") if d["event"] == planted[0]["id"] and d["field"] == "shares")
    assert talk["new"][planted[0]["payload"]["key"]] == {"claim": rumour, "share": 0.3}  # (then gossip has its way)


def test_structural_closes_a_pass(base):
    assert replay(base, "structural", "structural", "4A 2", ROUTE, {"open": False, "why": "a rockslide"}) == 0
    changed = [e for e in table(base, "structural", "events") if e["type"] == "geo.changed"]
    assert len(changed) == 1 and changed[0]["payload"]["why"] == "a rockslide"
    assert any(c[0] == "ripple" for c in changed[0]["causes"])


@pytest.mark.parametrize("kind, params", [
    ("favour", {"by": 0.5}), ("favour", {"by": 2, "until": [4, 5, 0]}), ("luck", {}), ("plant", {"share": 0.3}),
    ("plant", {"claim": {"pred": "killed", "args": {"victim": "x"}}}), ("plant", {"claim": {"pred": "omen", "args": {}}}),
    ("plant", {"claim": {"pred": "killed", "args": {"victim": "x", "by": "y"}}, "share": 2}),
    ("structural", {"why": "x"}), ("structural", {"open": "no"}), ("structural", {"days": -1})])
def test_a_ripple_without_its_params_is_refused(kind, params):
    from renasci.core.ripples import Ripple

    sc = copy.deepcopy(renascita.SCENARIO)
    sc["params"]["beliefs"] = True  # (so the plant disguise is there to refuse what it can't plant)
    with pytest.raises(ValueError):
        renascita.new_engine(seed=1, scenario=sc, ripples=[Ripple("r", kind, renascita.START, TOWN, params)])


def test_favour_and_luck_are_logged_as_applied(base):
    for run in ("favour", "luck"):
        apply = [r for r in table(base, run, "ripples") if r["action"] == "apply"]
        assert apply and all(r["applied"] for r in apply)


def test_a_reshuffle_from_year_x_rerolls_everything_after_and_the_diff_explains_it(base):
    from renasci.cli import main

    root, scenario = base
    (root / "again.toml").write_text(BODY.format(name="again", scenario=scenario)
                                     + '[[reshuffle]]\nfrom = "4A 3"\nsalt = "again"\n', encoding="utf-8")
    assert main(["replay", str(root / "runs" / "base"), "--recipe", str(root / "again.toml"),
                 "--out", str(root / "runs")]) == 0
    assert main(["diff", str(root / "runs" / "base"), str(root / "runs" / "again")]) == 0
    a = {e["id"]: e for e in table(base, "base", "events")}
    b = {e["id"]: e for e in table(base, "again", "events")}
    assert {i for i, e in a.items() if e["date"] < [4, 3, 0]} == {i for i, e in b.items() if e["date"] < [4, 3, 0]}
    assert {i for i, e in a.items() if e["date"] >= [4, 3, 0]} != {i for i, e in b.items() if e["date"] >= [4, 3, 0]}
