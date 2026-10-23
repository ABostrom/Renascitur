"""The people model's view of the vault (S2 spec §6, §8): births, reigns and who is placed at the start.

`people_hook(ctx)` is a `renasci.vault.pins.extract` hook. For each canon character note:

| The note says | It becomes |
|---|---|
| `died` before the run starts | **dead**: not placed, nothing pinned |
| `born` starting before the run (a year that spans the start counts) | **placed** at the start (casting, #63); an `<id>:alive` existence pin to the day before `died`, if it says when |
| `born` inside the run, and a `father` or `mother` | a **birth pin**: `people.birth` with the parents as roles and a bind of the child (`<id>:born`); **reserved** |
| `born` inside the run, no parent | **unplaced** (the engine has no way to bring them in yet) |
| no `born`, but a `house` | **drawn**: placed with an age drawn at casting, never canon |
| no `born`, no house | **unplaced** |
| `born` after the run | **out_of_scope** |
| `died` inside the run | an **expectation**, checked after the run (the engine never kills to order) |
| `offices: [{office, from, to}]` | a **reign pin** per reign (`people.succession`, successor = them, on the office's entity: a house's headship is `<house id>-head`), numbered per holder and office (`<id>:reign:<office>:<n>`), with orderings between consecutive reigns of the office |

A pin that can't be met is not made; a `doomed_*` finding says why instead: a reign by someone who is never
in the run or holds it before they're born; a birth whose parent never comes to be, is born after the
child, or is dead by then. A reign by someone outside the office's house is made but flagged
(`outside_house`): only the house's own line succeeds naturally, so it will be forced every time.
Consecutive reigns' windows are narrowed so each ends no later than the next one's.

`holders` (office -> character) records who holds each office when the run starts: the latest reign that
began before it. Casting places them in office.

A title office (an `organisation` with `kind: office`, such as the Emperors) has no office entity in the
people model yet, so its reigns are reported as unsupported, not pinned.
"""

from __future__ import annotations

from renasci.core.calendar import Date
from renasci.core.pins import Pin

OWNS = frozenset({"people.birth"})  # event types this hook owns: event notes can't pin them (§6)


def _day_before(calendar, d: Date) -> Date:
    return calendar.from_ordinal(d.age, calendar.ordinal(d) - 1)


def _window_json(w):
    return [d.to_json() for d in w] if w else None


def people_hook(ctx) -> None:
    people: dict[str, dict] = {}
    for key, note in ctx.notes("character"):
        cid = ctx.id_of(key)
        if cid is None:
            continue
        fm = note.frontmatter
        born, died = ctx.date(key, fm.get("born")), ctx.date(key, fm.get("died"))
        parents = {}
        for role in ("father", "mother"):
            pid = ctx.id_of(ctx.link(fm.get(role), {"character"}))
            if fm.get(role) is not None and pid is None:
                ctx.finding("not_canon_parent", key, f"{role}: {fm.get(role)!r} is not a canon character with an id")
            if pid:
                parents[role] = pid
        house = ctx.id_of(ctx.link(fm.get("house"), {"house"}))
        race = ctx.id_of(ctx.link(fm.get("race"), {"race"}))
        if died is not None and died[1] < ctx.start:
            status = "dead"
        elif born is None:
            status = "drawn" if house else "unplaced"
        elif born[0] <= ctx.start:
            status = "placed"
        elif born[0] > ctx.end:
            status = "out_of_scope"
        else:
            status = "reserved" if parents else "unplaced"
        people[cid] = {"key": key, "note": note, "status": status, "house": house, "born_w": born, "died_w": died,
                       "parents": parents, "sex": fm.get("sex") if fm.get("sex") in ("m", "f") else None}
        ctx.out.placements[cid] = {"status": status, "key": key, "house": house, "born": _window_json(born),
                                   "died": _window_json(died), "sex": people[cid]["sex"], "parents": parents,
                                   "race": race}

    for cid, p in people.items():
        key, born, died = p["key"], p["born_w"], p["died_w"]
        if p["status"] == "reserved":
            doomed = None
            for role, pid in sorted(p["parents"].items()):
                parent = people.get(pid)
                if parent is None or parent["status"] in ("unplaced", "out_of_scope", "dead"):
                    doomed = f"its {role} {pid} never comes to be in this run"
                elif parent["born_w"] is not None and parent["born_w"][0] >= born[1]:
                    doomed = f"its {role} {pid} is born after it"
                elif parent["died_w"] is not None and parent["died_w"][1] < born[0]:
                    doomed = f"its {role} {pid} is dead by then (S2 §8)"
            if doomed:
                ctx.finding("doomed_birth", key, f"{cid}: {doomed}")
            else:
                fields = {"sex": p["sex"]} if p["sex"] else {}
                ctx.anchors[key] = ctx.pin(Pin(f"{cid}:born", "event", window=born, payload={
                    "type": "people.birth", "roles": {r: [x] for r, x in sorted(p["parents"].items())},
                    "bind": {"role": "child", "subject": cid, "fields": fields}}))
        if p["status"] == "placed" and died is not None and died[0] > ctx.start:
            ctx.pin(Pin(f"{cid}:alive", "existence", subject=cid,
                        window=(ctx.start, min(_day_before(ctx.calendar, died[0]), ctx.end))))
        if died is not None and ctx.touches_run(died) and p["status"] != "dead":
            ctx.out.expectations.append({"kind": "died", "subject": cid, "key": key, "window": _window_json(died)})

    reigns: dict[str, list] = {}  # office entity id -> [(window, character id, key, house id)]
    for cid, p in people.items():
        key = p["key"]
        for entry in p["note"].frontmatter.get("offices") or []:
            if not isinstance(entry, dict) or "office" not in entry:
                ctx.finding("office", key, f"an office entry is {{office, from, to}}, got {entry!r}")
                continue
            okey = ctx.link(entry["office"], {"house", "organisation"})
            onote = ctx.vault.notes.get(okey) if okey else None
            oid = ctx.id_of(okey)
            if onote is None or oid is None:
                ctx.finding("office", key, f"{entry['office']!r} is not a canon house or office")
                continue
            if onote.type != "house":
                ctx.report("unsupported", key, f"a reign of {oid}: title offices have no office entity yet (S2 §7)")
                continue
            start = ctx.date(key, entry.get("from"))
            if start is None:
                ctx.finding("office", key, f"a reign of {oid} needs a `from` date")
                continue
            office = f"{oid}-head"
            if office in ctx.ids.values():
                ctx.finding("office", key, f"{office} is also a note's id: rename one")
                continue
            until = ctx.date(key, entry.get("to")) if entry.get("to") is not None else None
            row = {"office": office, "holder": cid, "key": key, "from": start, "to": until, "pin": None}
            ctx.out.reigns.append(row)
            reigns.setdefault(office, []).append((start, cid, key, oid, row))

    holders: dict[str, str] = {}
    for office, held in sorted(reigns.items()):
        held.sort(key=lambda r: (r[0][0], r[1]))
        before = [r for r in held if r[0][1] < ctx.start]
        if before:
            holders[office] = before[-1][1]
        counts: dict[str, int] = {}
        previous = None
        for i, (window, cid, key, house, row) in enumerate(held):
            counts[cid] = n = counts.get(cid, 0) + 1
            if i + 1 < len(held) and held[i + 1][0][1] < window[1]:
                window = (window[0], held[i + 1][0][1])  # end no later than the next reign's window
            p = people[cid]
            if p["status"] in ("unplaced", "out_of_scope", "dead") and ctx.touches_run(window):
                ctx.finding("doomed_reign", key, f"a reign of {office}: {cid} is never in the run ({p['status']})")
                previous = None
                continue
            if p["born_w"] is not None and window[1] < p["born_w"][0]:
                ctx.finding("doomed_reign", key, f"a reign of {office} from before {cid} is born")
                previous = None
                continue
            if p["house"] != house:
                ctx.finding("outside_house", key, f"{cid} reigns over {office} but isn't of that house: it will be forced")
            pin = ctx.pin(Pin(f"{cid}:reign:{office}:{n}", "event", window=window, payload={
                "type": "people.succession", "roles": {"successor": [cid]}, "office": office}))
            row["pin"] = pin.id
            if previous is not None:
                ctx.order(previous, pin, key, f"the reign before {cid}'s of {office}")
            previous = pin
    ctx.out.holders.update(holders)


people_hook.owns = OWNS


# ---------------------------------------------------------------- feasibility (S2 §8)


def _years(calendar, earlier, later) -> tuple[float, float]:
    """The least and most whole years from a date in window `earlier` to one in window `later`."""
    def days(a, b):
        return calendar.days_between(a, b) if a <= b else -calendar.days_between(b, a)

    per = calendar.days_per_year
    return days(earlier[1], later[0]) / per, days(earlier[0], later[1]) / per


def people_check(extraction, vault, races, report, calendar) -> None:
    """Lineages, lives, ages at a birth and reigns (S2 §8), marking pins infeasible in `report`."""
    from renasci.core.calendar import Date
    from renasci.vault.feasibility import infeasible

    people = extraction.placements

    def window(p, k):
        w = p.get(k)
        return (Date.from_json(w[0]), Date.from_json(w[1])) if w else None

    def pins_of(cid):
        return [pid for pid in report["pins"] if pid.startswith(f"{cid}:")]

    def finding(kind, key, message):
        report["findings"].append({"kind": kind, "key": key, "message": message})

    for cid, p in people.items():  # died before born: nothing about them can hold
        born, died = window(p, "born"), window(p, "died")
        if born and died and died[1] < born[0]:
            finding("died_before_born", p["key"], f"{cid} dies before being born")
            for pid in pins_of(cid):
                infeasible(report, pid, f"{cid} dies before being born", [p["key"]])

    state: dict[str, int] = {}  # lineage cycles: a DFS over every parent (0 visiting, 1 done)
    stack: list[str] = []
    cycles: list[list[str]] = []

    def visit(node):
        state[node] = 0
        stack.append(node)
        for parent in sorted(people[node].get("parents", {}).values()):
            if parent not in people:
                continue
            if state.get(parent) == 0:
                cycles.append(stack[stack.index(parent):])
            elif parent not in state:
                visit(parent)
        stack.pop()
        state[node] = 1

    for cid in sorted(people):
        if cid not in state:
            visit(cid)
    for cycle in cycles:
        keys = [people[m]["key"] for m in cycle]
        finding("lineage_cycle", keys[0], " -> ".join(cycle + [cycle[0]]))
        for member in cycle:
            infeasible(report, f"{member}:born", "a lineage cycle", keys)

    race_of = vault.config.races
    missing_race = False
    for cid, p in people.items():  # ages at a birth
        pid = f"{cid}:born"
        if pid not in report["pins"]:
            continue
        born = window(p, "born")
        for role, parent_id in sorted(p.get("parents", {}).items()):
            parent = people.get(parent_id)
            pborn = window(parent, "born") if parent else None
            if parent is None or pborn is None:
                continue
            race = races.get(race_of.get(parent.get("race"))) if races and parent.get("race") else None
            if race is None:
                missing_race = True
                continue
            try:
                lo, hi = _years(calendar, pborn, born)
            except ValueError:  # (born in different ages: ages across a boundary come with M7a)
                continue
            if role == "mother" and (hi < race.fertile[0] or lo >= race.fertile[1] + 1):
                infeasible(report, pid, f"its mother {parent_id} would be {lo:.0f}-{hi:.0f}, outside her race's "
                           f"fertile years {race.fertile[0]}-{race.fertile[1]}", [p["key"], parent["key"]])
            if role == "father" and hi < race.marriage[0]:
                infeasible(report, pid, f"its father {parent_id} would be at most {hi:.0f}, too young to marry "
                           f"({race.marriage[0]})", [p["key"], parent["key"]])
    if missing_race:
        report["reports"].append({"kind": "no_race_data", "key": None, "message":
                                  "some parents have no race the scenario knows (vault.toml [races]): their ages "
                                  "at a birth weren't checked"})

    by_office: dict[str, list] = {}
    for r in extraction.reigns:  # reigns: overlaps and outside a life
        by_office.setdefault(r["office"], []).append(r)
        holder = people.get(r["holder"])
        died = window(holder, "died") if holder else None
        if r["pin"] and died and r["from"][0] > died[1]:
            infeasible(report, r["pin"], f"{r['holder']} is dead before this reign begins", [r["key"]])
    for office, held in by_office.items():
        held.sort(key=lambda r: (r["from"][0], r["holder"]))
        holding = None  # the reign whose end is latest so far
        for r in held:
            if holding and holding["to"] and r["pin"] and holding["to"][0] > r["from"][1]:
                infeasible(report, r["pin"], f"{holding['holder']} still holds {office} until "
                           f"{holding['to'][0].to_json()}", [holding["key"], r["key"]])
            if r["to"] and (holding is None or holding["to"] is None or r["to"][0] > holding["to"][0]):
                holding = r
    for pid, entry in report["pins"].items():  # an ordering stands or falls with its two pins
        if ":before:" in pid and entry["verdict"] != "infeasible":
            before, after = pid.split(":before:")
            for end in (before, after):
                if report["pins"].get(end, {}).get("verdict") == "infeasible":
                    infeasible(report, pid, f"{end} can't hold", report["pins"][end]["notes"])


people_hook.check = people_check
