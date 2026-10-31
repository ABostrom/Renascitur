"""The possible graph (#162): what can lead to what, from what the code declares."""

import json
import sys
import textwrap

import pytest

from renasci import ecology, renascita
from renasci.analysis import graph
from renasci.analysis.graph import Link
from renasci.core.calendar import Span
from renasci.core.pools import base, load


@pytest.fixture(scope="module")
def scenario():
    sc = renascita._scenario(None, crafts=True)
    sc["params"]["ecology"] = {**ecology.DEFAULT, "famine": {}}
    return sc


@pytest.fixture(scope="module")
def edges(scenario):
    return graph.build([rs for _, rs in renascita.rulesets(scenario)], base())


def test_the_graph_shows_an_extensions_system(tmp_path, monkeypatch, capsys):
    from renasci.cli import main

    (tmp_path / "ext_bell.py").write_text(textwrap.dedent("""
        from renasci.core.events import EventType
        from renasci.core.systems import System


        class Bell(System):
            name, cadence = "beat.bell", "yearly"
            event_types = (EventType("beat.tolled", 1, roles={"place": (1, 1)}, payload={}),)


        def extend(pools):
            pools.systems.add(Bell)
    """), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["graph", "--extensions", "ext_bell", "--from", "system:beat.bell", "--to", "event:beat.tolled"]) == 0
    assert "beat.tolled" in capsys.readouterr().out
    sys.modules.pop("ext_bell", None)


def test_famine_reaches_plague_with_nothing_authored_on_the_way(edges):
    path = graph.emergent(edges, "system:ecology.famine", "event:disease.outbreak")
    assert path and all(e.kind in ("influence", "emit") for e in path)
    assert "field:hunger" in {e.b for e in path}  # (the short way: hunger speeds it)
    assert graph.emergent(edges, "system:ecology.famine", "stock:corpses")  # (the long way: the dead)
    assert graph.emergent(edges, "stock:corpses", "event:disease.outbreak")


def test_the_dead_reach_a_haunting(edges):
    assert graph.route(edges, "system:people.population", "mark:haunted")


def test_a_haunted_town_reaches_what_reads_danger(edges):
    path = graph.route(edges, "mark:haunted", "system:people.drives")
    assert [e.b for e in path] == ["field:danger", "system:people.drives"]


def test_plans_join_goals_to_actions(edges):
    assert graph.Edge("action:Flee", "goal:safe", "plan") in edges


def test_what_nothing_joins_has_no_route(edges):
    assert graph.route(edges, "goal:safe", "stock:corpses") is None


def test_an_event_routes_from_what_emits_it(edges):
    assert graph.route(edges, "event:goods.eaten", "event:disease.outbreak")


def test_burial_reaches_plague_through_the_dead(edges):
    assert [e.b for e in graph.emergent(edges, "system:ecology.burial", "system:ecology.disease")] == ["stock:corpses", "system:ecology.disease"]


def test_what_each_system_moves_it_declares(scenario):
    sc = dict(scenario)
    e = renascita.new_engine(seed=3, scenario=sc)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=12)))
    assert e.fed
    declared = {s.name: set(s.feeds) for _, rs in e.rulesets for s in (*rs.systems, *rs.disguises, *rs.forcers)}
    for system, stock in sorted(e.fed):
        assert stock in declared[system], (system, stock)


def test_a_war_shows_in_the_graph():
    sc = renascita._scenario(None, polities=True)
    sc["params"]["campaigns"] = True
    every = graph.build([rs for _, rs in renascita.rulesets(sc)], base())
    assert graph.Edge("system:polity.war", "stock:corpses", "influence") in every
    assert graph.Edge("system:polity.campaigns", "stock:corpses", "influence") in every


def test_common_fields_are_left_out_unless_asked_for(scenario, edges):
    assert "field:status" not in {e.a for e in edges}
    every = graph.build([rs for _, rs in renascita.rulesets(scenario)], base(), include_common=True)
    assert "field:status" in {e.a for e in every}


def test_wildcards_name_no_field(edges):
    assert not [e for e in edges if e.a.endswith("*") or e.b.endswith("*")]


LINKS = """
    from renasci.analysis.graph import Link
    from renasci.core.events import EventType
    from renasci.core.pools import Reaction

    BEAT = EventType("beat.x", 1, roles={"who": (1, 1)}, payload={}, dead_roles=("who",))


    def extend(pools):
        pools.event_types.add(BEAT)
        pools.reactions.add(Reaction("r", "people.death", print, emits=("beat.x",)))
        pools.links.add(Link("people.death", "beat.x", why="grief", weight=0.3))
        pools.links.add(Link("famine.began", "polity.nothing", why="a typo"))
        pools.links.add(Link("goal:safe", "famine.began", why="wishful"))
"""


@pytest.fixture
def extended(tmp_path, monkeypatch, scenario):
    (tmp_path / "ext_links.py").write_text(textwrap.dedent(LINKS), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    yield graph.build([rs for _, rs in renascita.rulesets(scenario)], load(["ext_links"]))
    sys.modules.pop("ext_links", None)


def test_reactions_and_links_join_the_graph_with_where_they_came_from(extended):
    trigger = [e for e in extended if e.kind == "trigger"]
    assert {(e.a, e.b) for e in trigger} == {("event:people.death", "reaction:r"), ("reaction:r", "event:beat.x")}
    link = next(e for e in extended if e.kind == "explicit" and e.why == "grief")
    assert link.origin == "ext_links" and link.a == "event:people.death"


def test_the_check_finds_links_that_mean_nothing(extended):
    found = graph.check(extended, set(base().goals))
    assert found["goals_nothing_achieves"] == []
    assert "goal:tie" in graph.check(extended)["goals_nothing_achieves"]  # (no action does: the world does)
    assert "event:famine.began -> event:polity.nothing" in found["links_to_nothing"]
    assert "goal:safe -> event:famine.began" in found["links_without_a_route"]
    assert "event:people.death -> event:beat.x" not in found["links_without_a_route"]


def test_a_link_can_name_any_node():
    assert graph.node("people.death") == "event:people.death"
    assert graph.node("stock:corpses") == "stock:corpses"
    assert Link("a", "b").name == "a -> b"


def test_a_run_shows_what_fired_and_what_never_did(extended):
    e = renascita.new_engine(seed=3)
    e.run(until=renascita.CAL.add(renascita.START, Span(years=3)))
    rows = [x.to_json() for x in e.events]
    assert rows and "causes" in rows[0]
    found = graph.overlay(rows, extended)
    assert found["fired"] and all(row["count"] > 0 for row in found["fired"])
    assert "event:people.death -> event:beat.x" in found["links_never_seen"]


def test_the_command_finds_a_route(capsys):
    from renasci.cli import main

    assert main(["graph", "--world", "fourth_age", "--crafts", "--ecology", "--emergent",
                 "--from", "system:ecology.famine", "--to", "event:disease.outbreak"]) == 0
    assert "system:ecology.disease" in capsys.readouterr().out


def test_the_command_refuses_what_it_cannot_do(capsys):
    from renasci.cli import main

    assert main(["graph", "--world", "fourth_age", "--from", "event:people.death", "--to", "stock:nothing"]) == 1
    assert main(["graph", "--world", "fourth_age", "--from", "event:people.death"]) == 1
    assert main(["graph", "--world", "kin", "--crafts"]) == 1
    assert main(["graph", "--world", "fourth_age", "--ecology", "--check"]) == 0


def test_the_command_checks(capsys):
    from renasci.cli import main

    assert main(["graph", "--world", "fourth_age", "--check"]) == 0
    assert "goals_nothing_achieves" in json.loads(capsys.readouterr().out)
