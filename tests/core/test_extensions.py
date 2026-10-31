import json
import subprocess
import sys
import textwrap

import pytest

from renasci import renascita
from renasci.core.calendar import Span
from renasci.core.pools import base, load, pools
from renasci.io.recipe import parse_recipe

BEATS = """
    from renasci.core.events import EventType
    from renasci.people.actions import Action
    from renasci.people.ambitions import Ambition, Formation

    SWORN = EventType("beat.sworn", 1, roles={"who": (1, 1), "vow": (1, 1)}, payload={})


    class Swear(Action):
        name, achieves, duration_days = "Swear", "sworn", 30
        reads = frozenset({"oath_read"})
        writes = frozenset({"new:vow"})

        def possible(self, ctx, actor, target, scheme):
            return True

        def odds(self, ctx, actor, target, scheme):
            return 1.0

        def succeed(self, ctx, actor, target, scheme, event):
            ctx.emit("beat.sworn", {"who": (actor,)}, purpose="swear", actor=actor, creates={"vow": [("vow", {})]})


    class Oath(Ambition):
        name, cooldown_years = "Oath", 50

        def eligible(self, ctx, person):
            return Formation(ctx.get(person, "place"), ("drive", "status"))

        def urge(self, ctx, person):
            return 1.0

        def subgoals(self, ctx, amb):
            return [frozenset({"sworn"})]

        def text(self, ctx, owner, target):
            return "swear an oath"


    def extend(pools):
        pools.actions.add(Swear)
        pools.ambitions.add(Oath)
        pools.event_types.add(SWORN)
"""


@pytest.fixture
def beats(tmp_path, monkeypatch):
    (tmp_path / "ext_beats.py").write_text(textwrap.dedent(BEATS), encoding="utf-8")
    (tmp_path / "ext_empty.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    yield "ext_beats"
    for m in ("ext_beats", "ext_empty"):
        sys.modules.pop(m, None)


def years(e, n):
    e.run(until=renascita.CAL.add(renascita.START, Span(years=n)))
    return e


def of(e, kind):
    return [x for x in e.events if x.type == kind]


def test_base_holds_every_pool_whatever_was_imported():
    found = base()
    assert "Duel" in found.actions and "Marry" in found.ambitions
    assert found.describe()["actions"]["Duel"] == "base"


def test_load_copies_the_base_and_leaves_it_alone(beats):
    mine = load(["ext_beats"])
    assert "Swear" in mine.actions and "Oath" in mine.ambitions and "beat.sworn" in mine.event_types
    assert "Swear" not in pools.actions and mine.actions.frozen
    assert mine.describe()["actions"]["Swear"] == "ext_beats" and mine.describe()["actions"]["Duel"] == "base"


def test_an_extension_must_have_extend(beats):
    with pytest.raises(ValueError, match="ext_empty.*extend"):
        load(["ext_empty"])


def test_a_missing_extension_says_so(beats):
    with pytest.raises(ValueError, match="ext_missing"):
        load(["ext_missing"])


def test_an_extension_cannot_replace_a_base_entry(tmp_path, monkeypatch):
    (tmp_path / "ext_clash.py").write_text(textwrap.dedent("""
        from renasci.people.actions import ACTIONS

        def extend(pools):
            pools.actions.add(ACTIONS["Duel"])
    """), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="Duel"):
        load(["ext_clash"])
    sys.modules.pop("ext_clash", None)


def test_a_pool_cannot_hide_a_registry_method():
    from renasci.core.pools import Pools

    with pytest.raises(ValueError, match="values"):
        Pools().define("values")


def test_a_named_extension_works_end_to_end_with_no_engine_edits(beats):
    e = renascita.new_engine(seed=3)
    e.extend(["ext_beats"])
    years(e, 3)
    assert [x for x in of(e, "people.ambition_formed") if x.payload["class"] == "Oath"]
    assert of(e, "beat.sworn")


def test_an_extension_reaches_only_the_engine_that_names_it(beats):
    with_it = renascita.new_engine(seed=3)
    with_it.extend(["ext_beats"])
    without = renascita.new_engine(seed=3)
    plain = renascita.new_engine(seed=3)
    years(with_it, 1), years(without, 1), years(plain, 1)
    assert [x.id for x in without.events] == [x.id for x in plain.events]
    assert not of(without, "beat.sworn")


def test_an_extended_run_replays_identically(beats):
    a, b = (renascita.new_engine(seed=3) for _ in range(2))
    a.extend(["ext_beats"]), b.extend(["ext_beats"])
    years(a, 2), years(b, 2)
    assert [x.id for x in a.events] == [x.id for x in b.events]


def test_the_extension_and_its_source_are_in_the_recipe(beats, tmp_path):
    e = renascita.new_engine(seed=3)
    assert "extensions" not in e.recipe()
    e.extend(["ext_beats"])
    first = e.recipe()["extensions"]
    assert first[0][0] == "ext_beats"
    (tmp_path / "ext_beats.py").write_text(textwrap.dedent(BEATS) + "\n# edited\n", encoding="utf-8")
    e2 = renascita.new_engine(seed=3)
    e2.extend(["ext_beats"])
    assert e2.recipe()["extensions"] != first


def test_the_digest_covers_a_helper_beside_the_extension(beats, tmp_path):
    from renasci.core.pools import source_digest

    helper = tmp_path / "ext_helper.py"
    helper.write_text("VALUE = 1\n", encoding="utf-8")
    first = source_digest("ext_beats")
    helper.write_text("VALUE = 2\n", encoding="utf-8")
    assert source_digest("ext_beats") != first


def test_an_extension_keeping_instance_state_cannot_checkpoint(beats):
    e = renascita.new_engine(seed=3)
    e.extend(["ext_beats"])
    e.pools.actions["Swear"].count = 1
    with pytest.raises(ValueError, match="Swear keeps instance state"):
        e.checkpoint(renascita.START, 0)
    del e.pools.actions["Swear"].count


def run_recipe(tmp_path, name, end="4A 4", extension="ext_beats"):
    path = tmp_path / f"{name}.toml"
    path.write_text(textwrap.dedent(f"""
        [run]
        name = "{name}"
        engine = "0.1.0"
        seed = 3
        world = "fourth_age"
        end = "{end}"
        checkpoint_every_years = 1
        extensions = ["{extension}"]
    """), encoding="utf-8")
    return str(path)


def manifest(folder):
    return json.loads((folder / "manifest.json").read_text(encoding="utf-8"))


def test_an_extended_run_replays_from_a_checkpoint_and_an_edit_is_refused(beats, tmp_path):
    from renasci.cli import main

    out = tmp_path / "runs"
    assert main(["run", run_recipe(tmp_path, "first"), "--out", str(out)]) == 0
    first = manifest(out / "first")
    assert first["meta"]["pools"]["actions"]["Swear"] == "ext_beats" and first["meta"]["extensions"][0][0] == "ext_beats"
    assert main(["replay", str(out / "first"), "--recipe", run_recipe(tmp_path, "second"), "--from", "4A 2", "--out", str(out)]) == 0
    assert manifest(out / "second")["meta"]["state_hash"] == first["meta"]["state_hash"]
    (tmp_path / "ext_beats.py").write_text(textwrap.dedent(BEATS) + "\n# edited\n", encoding="utf-8")
    assert main(["replay", str(out / "first"), "--recipe", run_recipe(tmp_path, "third"), "--from", "4A 2", "--out", str(out)]) == 1


def test_a_data_pool_can_keep_fields_and_still_checkpoint(tmp_path, monkeypatch):
    (tmp_path / "ext_data.py").write_text(textwrap.dedent("""
        class Trait:
            def __init__(self, name):
                self.name = name

        def extend(pools):
            pools.define("traits").add(Trait("keen"))
    """), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from renasci.cli import main

    assert main(["run", run_recipe(tmp_path, "data", extension="ext_data"), "--out", str(tmp_path / "runs")]) == 0
    sys.modules.pop("ext_data", None)


def test_the_pools_command_refuses_a_bad_name(capsys):
    from renasci.cli import main

    assert main(["pools", "../bad"]) == 1


def test_extending_a_started_engine_is_refused(beats):
    e = years(renascita.new_engine(seed=3), 1)
    with pytest.raises(ValueError, match="started"):
        e.extend(["ext_beats"])


def recipe(**run):
    return {"run": {"name": "x", "engine": "0.1.0", "seed": 1, "world": "toy", "end": "1X 2", **run}}


def test_a_recipe_names_its_extensions():
    assert parse_recipe(recipe(extensions=["my_beats", "pkg.more"])).extensions == ("my_beats", "pkg.more")
    assert parse_recipe(recipe()).extensions == ()


@pytest.mark.parametrize("bad", ["my_beats", [1], ["../evil"], ["a", "a"]])
def test_a_recipe_refuses_bad_extensions(bad):
    with pytest.raises(ValueError, match="extensions"):
        parse_recipe(recipe(extensions=bad))


def test_the_pools_command_lists_every_pool():
    out = subprocess.run([sys.executable, "-X", "utf8", "-m", "renasci.cli", "pools"], capture_output=True, text=True,
                         check=True).stdout
    found = json.loads(out)
    assert found["actions"]["Duel"] == "base" and found["ambitions"]["Marry"] == "base"
