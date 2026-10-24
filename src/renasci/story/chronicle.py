"""POV chronicles (S12 spec §3, #116): a context pack told as an in-world account, the version its author
believes.

The author is the pack's point of view: a person, a house, a settlement (its masses' talk), or omniscient
(the plain truth, as a check). **Their account** holds one claim per question (`beliefs.topic`): the one
they hold firmest (a settlement: its largest share; a house: its head's, as the pack chose). An author
who **told a lie** on a question (a `belief.told` with `intent: "lie"`, the author as teller, for a house
its head, by the date the subject's beliefs are taken at) tells their lie instead, whatever they believe:
the victor's account.

**The telling:** a paragraph a year, in date order (a cause before what it caused, on one day too), a
sentence per event from its reading. Where the account holds a claim about an event (whose doing it was,
who killed whom), the claim follows the event's sentence, stated as fact, and a death the author has a
claim about is told without its real killer. **Silence:** only the pack's events are told (what the
author could know), never the talk itself (`belief.*`), and never a secret one: a chronicle is written to
be read. (The omniscient record keeps the secrets: it is what happened.) The title is the subject's
only where the chronicle tells it. **Slant**, plain: among events of one moment, the author's house
comes first.

The front matter is a vault chronicle (`type: chronicle`, `canon: proposed`, never canon): whose account,
the run's manifest digest and engine (no timestamps), and **divergence**: each stated claim that is false
or half true, with the events that tell the truth (`truth.judge`). Same pack, same bytes.
"""

from __future__ import annotations

import re

from renasci.analysis.truth import judge
from renasci.core.calendar import Calendar, Date
from renasci.core.canon import digest
from renasci.people import beliefs as B
from renasci.story.pack import Run, _head, build, end_of
from renasci.story.text import claim_text, reading

LIE = "lie"
WRONG = ("false", "half")
CONTROL = re.compile(r"[\x00-\x1f\x7f  ]")


def _q(text: str) -> str:
    """A double-quoted YAML scalar on one line: no name or claim can close it, break it or add a key."""
    return '"' + CONTROL.sub(" ", str(text)).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _sentence(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] + ("" if text.endswith((".", "!", "?")) else ".")


def _tellers(run: Run, pack: dict) -> set[str]:
    pov = pack["pov"]
    if pov["kind"] == "person":
        return {pov["id"]}
    if pov["kind"] == "house":  # (the house's voice: its head's lies, not any member's)
        head = _head(run, pov["id"])
        return {head} if head else set()
    return set()


def account(run: Run, pack: dict, end: list) -> dict[str, dict]:
    """The author's claim on each question: {topic: claim}. Omniscient holds none (it tells what happened)."""
    if pack["pov"]["kind"] == "omniscient":
        return {}
    chosen: dict[str, tuple] = {}
    for b in pack["beliefs"]:
        t = B.topic(b["claim"])
        rank = (-b["conf"], b["key"])
        if t not in chosen or rank < chosen[t][0]:
            chosen[t] = (rank, b["claim"])
    out = {t: c for t, (_, c) in chosen.items()}
    tellers = _tellers(run, pack)
    for e in run.events:  # (date order: a later lie on a question replaces an earlier one)
        if e["date"] > end:
            break
        if tellers and e["type"] == "belief.told" and e["payload"].get("intent") == LIE and \
                tellers & set(e["roles"].get("teller", [])):
            out[B.topic(e["payload"]["claim"])] = e["payload"]["claim"]
    return out


def _attached(run: Run, claims: dict[str, dict]) -> dict[str, list[dict]]:
    """Which event each claim is told with: a `why:` question with its event, a `killed:` one with the death."""
    deaths = {p: e["id"] for e in run.events if e["type"] == "people.death" for p in e["roles"].get("deceased", [])}
    out: dict[str, list[dict]] = {}
    for t, c in sorted(claims.items()):
        kind, _, about = t.partition(":")
        at = about if kind == "why" else deaths.get(about) if kind == "killed" else None
        if at:
            out.setdefault(at, []).append(c)
    return out


def _when(run: Run, date: list) -> str:
    cal = run.manifest.get("meta", {}).get("calendar")
    if cal:
        return Calendar.from_json(cal).format(Date.from_json(date))
    return f"{date[0]}:{date[1]}"


def _depths(run: Run, ids) -> dict[str, int]:
    """Each event's depth in the run's same-day cause graph (a cause is told before what it caused, even
    through links the author can't see: order only, never content). Iterative: chains can be long."""
    depth: dict[str, int] = {}
    for start in ids:
        stack = [(start, False)]
        while stack:
            i, done = stack.pop()
            ev = run.by_id[i]
            same = [r for k, r in ev.get("causes") or [] if k == "event" and r in run.by_id
                    and run.by_id[r]["date"] == ev["date"]]
            if done:
                depth[i] = 1 + max((depth.get(r, 0) for r in same), default=0)
            elif i not in depth:
                depth[i] = 0  # (a guard: a cycle counts as no deeper)
                stack.append((i, True))
                stack += [(r, False) for r in same if r not in depth]
    return depth


def _telling(run: Run, ev: dict, claims: list[dict]) -> str:
    """An event's reading; with a claim on who killed, without the real killer (the claim says who)."""
    full = run.by_id[ev["id"]]
    if any(c["pred"] == "killed" for c in claims) and "killer" in (full.get("roles") or {}):
        full = {**full, "roles": {k: v for k, v in full["roles"].items() if k != "killer"}}
        return reading(full, run.names, run.by_id) or ev["text"]
    return ev["text"]


def chronicle(run: Run, subject: tuple[str, str], pov: str = "omniscient") -> dict:
    """{"text": the Markdown chronicle, "divergence": [{event, said, verdict, truth}], "pack": the pack}."""
    pack = build(run, subject, pov)
    claims = _attached(run, account(run, pack, end_of(run, subject)))
    author = pack["pov"]
    house = author["id"] if author["kind"] == "house" else run.houses.get(author["id"] or "")
    ours = {p for p, h in run.houses.items() if house and h == house}
    omniscient = author["kind"] == "omniscient"
    depth = _depths(run, [ev["id"] for ev in pack["events"]])
    years: dict[tuple, list[tuple]] = {}
    told: dict[str, str] = {}
    divergence = []
    for ev in pack["events"]:
        if (ev["secret"] and not omniscient) or ev["type"].startswith("belief.") or not ev["text"]:
            continue
        mine = claims.get(ev["id"], [])
        told[ev["id"]] = _telling(run, ev, mine)
        said = [_sentence(told[ev["id"]])]
        for c in mine:
            text = claim_text(c, run.names, run.by_id)
            said.append(_sentence(text))
            verdict, evidence = judge(c, run.events, run.houses, log=run.log)
            if verdict in WRONG:  # (the events that tell the truth: for a death, the death itself)
                divergence.append({"event": ev["id"], "said": text, "verdict": verdict,
                                   "truth": sorted(set(evidence) - {ev["id"]}) or sorted(evidence)})
        ours_ = any(m in ours for ms in ev["roles"].values() for m in ms)
        years.setdefault(tuple(ev["date"][:2]), []).append((ev["date"], depth[ev["id"]], not ours_, ev["id"], " ".join(said)))
    sub = pack["subject"]
    about = sub["id"] if sub["kind"] == "event" else sub["id"].split(":", 1)[-1] if sub["kind"] == "topic" else None
    if about is not None and about in run.by_id and about not in told:
        heading = f"An account of {author['name']}" if not omniscient else "What happened"  # (nothing given away)
    elif sub["kind"] == "event":
        heading = _sentence(told[about]).rstrip(".")
    else:
        heading = sub["title"]
    whose = "what happened" if omniscient else f"the account of {author['name']}"
    title = heading if heading.startswith(("An account", "What happened")) else f"{heading} ({whose})"
    fm = ["---", "type: chronicle", "canon: proposed", f"title: {_q(title)}", "author:", f"  kind: {author['kind']}",
          *([f"  id: {_q(author['id'])}"] if author["id"] else []), f"  name: {_q(author['name'])}",
          "subject:", f"  kind: {sub['kind']}", f"  id: {_q(sub['id'])}",
          "source:", f"  run: {_q(run.name)}", f"  manifest: {_q(digest(run.manifest))}",
          f"  engine: {_q(str(run.manifest.get('engine')))}"]
    if divergence:
        fm.append("divergence:")
        fm += [f"  - {_q(f'{d['event']} ({d['verdict']}): {d['said']}; the truth: {', '.join(d['truth'])}')}"
               for d in divergence]
    else:
        fm.append("divergence: []")
    fm.append("---")
    voice = "the record" if omniscient else f"{whose}: what they believed and said, not what happened"
    body = [f"# {heading}", "", f"*{_sentence(voice)} Generated from the run {run.name}; not canon.*", ""]
    for (age, year), lines in sorted(years.items()):
        body.append(f"**{_when(run, [age, year, 0])}.** " + " ".join(s for *_, s in sorted(lines)))
        body.append("")
    return {"text": "\n".join(fm + body), "divergence": divergence, "pack": pack, "title": title}
