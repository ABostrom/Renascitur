"""The campaign brief (S12 spec §6, #119): a saga or an event laid out for a game, from the omniscient pack, on
the M4 run: every section, footnotes that are real events, hooks that name real open threads."""

import re

from renasci.story.brief import SECTIONS, brief
from renasci.story.pack import build


def failure(run):
    return next(e for e in run.events if e["type"] == "ward.failure")


def section(text, name):
    part = text.split(f"## {name}\n", 1)[1]
    return part.split("\n## ", 1)[0]


def test_the_top_saga_has_every_section(m4run):
    saga = m4run.stories["sagas"][0]
    doc = brief(m4run, ("saga", saga["id"]))
    for name in SECTIONS:
        assert f"## {name}\n" in doc["text"] and section(doc["text"], name).strip(), name
    assert saga["title"] in section(doc["text"], "Premise")


def test_footnotes_are_the_runs_events_and_all_defined(m4run):
    doc = brief(m4run, ("saga", m4run.stories["sagas"][0]["id"]))
    used = set(re.findall(r"\[\^([^\]]+)\](?!:)", doc["text"]))
    defined = set(re.findall(r"^\[\^([^\]]+)\]:", doc["text"], re.M))
    assert used and used == defined and used <= set(m4run.by_id)


def test_hooks_name_real_open_threads_as_they_stood_at_the_end(m4run):
    subject = ("saga", m4run.stories["sagas"][0]["id"])
    doc = brief(m4run, subject)
    end = build(m4run, subject)["span"][1]
    hooks = section(doc["text"], "Hooks")
    assert doc["threads"] and all(t["text"] in hooks for t in doc["threads"])
    for t in doc["threads"]:  # (open then: its people alive, its events past)
        assert all(m4run.died.get(p) is None or m4run.died[p] > end for p in t["people"] if p in m4run.ents)
        assert all(m4run.by_id[x]["date"] <= end for x in t["events"])


def test_npcs_can_be_told_apart_and_nothing_comes_from_after_the_span(m4run):
    for saga in m4run.stories["sagas"]:
        subject = ("saga", saga["id"])
        doc = brief(m4run, subject)
        npcs = re.findall(r"^- \*\*(.+?)\*\*", section(doc["text"], "NPCs"), re.M)
        assert len(npcs) == len(set(npcs)), npcs
        end = doc["pack"]["span"][1]
        cited = re.findall(r"\[\^([^\]]+)\]", section(doc["text"], "NPCs"))
        assert all(m4run.by_id[c]["date"] <= end for c in cited)


def test_the_ward_failure_brief_has_the_lie_and_its_truth(m4run):
    doc = brief(m4run, ("event", failure(m4run)["id"]))
    beliefs = section(doc["text"], "What people believe")
    assert "fault of" in beliefs and "false" in beliefs
    assert "fault of" in section(doc["text"], "Hooks")  # (a lie a truth could overturn)
    assert "had the ward-stones cracked" in section(doc["text"], "What really happened")  # (the GM's truth: secrets too)


def test_the_npcs_are_alive_at_the_end(m4run):
    subject = ("saga", m4run.stories["sagas"][0]["id"])
    doc = brief(m4run, subject)
    end = build(m4run, subject)["span"][1]
    for pid in doc["npcs"]:
        died = m4run.died.get(pid)
        assert died is None or died > end


def test_same_run_same_bytes(m4run):
    subject = ("event", failure(m4run)["id"])
    assert brief(m4run, subject)["text"] == brief(m4run, subject)["text"]


def test_renasci_brief_writes_it(m4):
    from renasci.cli import main
    from renasci.story.pack import Run

    run = Run(m4)
    assert main(["brief", str(m4), "--saga", run.stories["sagas"][0]["id"]]) == 0
    [out] = (m4 / "analysis" / "briefs").glob("saga-*.md")
    assert "## Hooks" in out.read_text(encoding="utf-8")
    assert main(["brief", str(m4)]) != 0
