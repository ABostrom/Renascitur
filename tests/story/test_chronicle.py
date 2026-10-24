"""POV chronicles (S12 spec §3, #116): a pack told as its author believes it, on the M4 run's ward failure.
The town, a townsman told the lie and the guild master who told it all tell the lie, and list where it
departs from the truth; the spared leader, who saw the sabotage, tells the truth."""

from renasci.story.chronicle import chronicle
from renasci.story.pack import Run
from renasci.vault.frontmatter import parse

TOWN = "v:lux-oescus"


def failure(run):
    return next(e for e in run.events if e["type"] == "ward.failure")


def the_lie(run):
    return next(e for e in run.events if e["type"] == "belief.told" and e["payload"].get("intent") == "lie")


def told(run, pov):
    return chronicle(run, ("event", failure(run)["id"]), pov)


def blamed(run):
    return run.names(the_lie(run)["payload"]["claim"]["args"]["party"])


def saboteur(run):
    return run.names.full(next(e for e in run.events if e["type"] == "ward.sabotage")["roles"]["ordered_by"][0])


def body(doc):
    """The told paragraphs, without the front matter and title."""
    return "\n".join(line for line in doc["text"].split("\n") if line.startswith("**"))


def assert_tells_the_lie(run, doc):
    fail = failure(run)
    assert f"fault of {blamed(run)}" in doc["text"]
    wrong = [d for d in doc["divergence"] if d["event"] == fail["id"]]
    assert wrong and wrong[0]["verdict"] == "false"
    sabotage = next(e for e in run.events if e["type"] == "ward.sabotage")
    assert sabotage["id"] in wrong[0]["truth"]  # (the event that tells the truth)


def test_the_town_tells_the_official_line(m4run):
    assert_tells_the_lie(m4run, told(m4run, TOWN))


def test_a_townsman_told_the_lie_tells_it(m4run):
    lie = the_lie(m4run)
    hearer = next(h for e in m4run.events if e["type"] == "belief.told" and e["payload"].get("intent") == "lie"
                  for h in e["roles"]["holder"] if h in m4run.ents and m4run.ents[h]["kind"] == "person"
                  and h != lie["roles"]["teller"][0])
    assert_tells_the_lie(m4run, told(m4run, hearer))


def test_the_guild_master_tells_his_lie_not_what_he_believes(m4run):
    master = the_lie(m4run)["roles"]["teller"][0]
    doc = told(m4run, master)
    assert_tells_the_lie(m4run, doc)
    assert "caused the ward failure" not in body(doc)  # (he knows better, and says otherwise)


def test_the_spared_leader_tells_the_truth(m4_spared):
    run = Run(m4_spared)
    leader = failure(run)["roles"]["leader"][0]
    doc = told(run, leader)
    assert f"{saboteur(run)} caused the ward failure" in body(doc) and f"fault of {blamed(run)}" not in body(doc)
    assert not [d for d in doc["divergence"] if d["event"] == failure(run)["id"]]


def test_secrets_stay_out_and_the_far_away_know_nothing(m4run):
    fail = failure(m4run)
    for pov in (TOWN, the_lie(m4run)["roles"]["teller"][0]):
        assert not any(e["secret"] and e["text"] in body(told(m4run, pov)) for e in told(m4run, pov)["pack"]["events"])  # (the sabotage is secret: never narrated)
    far = next(p for p, e in sorted(m4run.ents.items()) if e["kind"] == "person"
               and all(place != TOWN for _, place in m4run.residence(p))
               and m4run.houses.get(p) not in {m4run.houses.get(m) for ms in fail["roles"].values() for m in ms}
               and not any(p in ms for ms in fail["roles"].values()))
    assert "ward" not in body(told(m4run, far)).lower()


def _sentence_of(run, ev):
    from renasci.story.text import reading

    text = reading(ev, run.names, run.by_id)
    return text[:1].upper() + text[1:]


def test_an_omniscient_chronicle_has_nothing_to_diverge(m4run):
    doc = told(m4run, "omniscient")
    sabotage = next(e for e in m4run.events if e["type"] == "ward.sabotage")
    assert doc["divergence"] == [] and _sentence_of(m4run, sabotage) in body(doc)  # (the record keeps the secrets)


def test_it_is_a_vault_chronicle_never_canon_and_the_same_bytes_twice(m4run):
    doc = told(m4run, TOWN)
    assert doc["text"] == told(m4run, TOWN)["text"]
    fm = parse(doc["text"])[0]
    assert fm["type"] == "chronicle" and fm["canon"] == "proposed"
    assert fm["source"]["run"] == "m4" and fm["author"]["id"] == TOWN
    assert [s.split(" ")[0] for s in fm["divergence"]] == [d["event"] for d in doc["divergence"]]
    assert parse(doc["text"])[1] == []  # (the vault reads it without findings)


def test_renasci_chronicle_writes_it(m4):
    from renasci.cli import main

    fail = failure(Run(m4))
    assert main(["chronicle", str(m4), "--event", fail["id"], "--pov", TOWN]) == 0
    written = list((m4 / "analysis" / "chronicles").glob("event-*--v_lux-oescus.md"))
    assert len(written) == 1 and "chronicle" in written[0].read_text(encoding="utf-8")
    assert main(["chronicle", str(m4), "--event", fail["id"], "--pov", "p:nobody"]) != 0
