"""Pins from the vault (S2 spec §6): canon notes → S1 pins, for one run's window.

The core is world-agnostic. It makes **event pins** from event notes that name an engine event type
(`engine:`), lists the rest as **unmodelled**, and makes **orderings** from `before:`/`after:` links.
**Hooks** add what a world's people model knows (`renasci.people.vault.people_hook`: births with binds,
reigns, who is placed at the start).

Rules that keep the engine honest:

- only S1's supported kinds come out (`existence`, `event`, `ordering`);
- an ordering is a pin only between two event pins that both touch the run; otherwise the bridge checks
  the two windows itself and reports the ordering met, or infeasible;
- a pin that names a non-canon participant is not made (a finding says why).

Pin ids are `<note id>:<what>` (`v:wedding-of-bryn:event`, `v:a:before:v:b`), so each traces to a note.
Notes are named by their ids, written or as `ids.assign` would give them, so extraction works before the
id migration has run.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from renasci.core.calendar import Date
from renasci.core.pins import Pin
from renasci.vault.dates import AgeTable, parse_date
from renasci.vault.ids import assign
from renasci.vault.mapping import role


@dataclass
class Extraction:
    pins: list = field(default_factory=list)
    placements: dict = field(default_factory=dict)  # canon id -> {status, key, ...} (hooks; casting reads it)
    expectations: list = field(default_factory=list)  # checked after a run: {kind, subject, window}
    unmodelled: list = field(default_factory=list)  # event notes the engine can't yet tell
    reports: list = field(default_factory=list)  # informational: {kind, key, message}
    findings: list = field(default_factory=list)  # problems: {kind, key, message}
    holders: dict = field(default_factory=dict)  # office -> who holds it when the run starts (hooks)

    def to_json(self) -> dict:
        return {"pins": [p.to_json() for p in self.pins], "placements": self.placements, "holders": self.holders,
                "expectations": self.expectations, "unmodelled": self.unmodelled, "reports": self.reports,
                "findings": self.findings}


class Context:
    """What a hook sees: the vault, ids, dates and the run's window, and where to put what it makes."""

    def __init__(self, vault, calendar, start: Date, end: Date, owned=frozenset()):
        self.vault, self.calendar, self.start, self.end = vault, calendar, start, end
        self.owned = frozenset(owned)  # event types the hooks own: event notes can't pin them
        self.ids = assign(vault)
        self.out = Extraction()
        self.anchors: dict[str, Pin] = {}  # note key -> the event pin that stands for it in orderings
        starts = dict(vault.config.ages)
        for note in vault.notes.values():  # era notes say where their age starts ("The Fourth Age")
            if note.type == "era" and isinstance(note.frontmatter.get("aat-event-start-date"), int):
                age = next((a for a in calendar.ages if f"The {a.name}" == note.title), None)
                if age is not None:
                    starts.setdefault(age.abbrev, note.frontmatter["aat-event-start-date"])
        self.ages = AgeTable(starts)

    def notes(self, *types: str):
        """Canon pin-source notes of these types, in key order."""
        for key, note in self.vault.notes.items():
            if note.type in types and role(note) == "pin_source":
                yield key, note

    def id_of(self, key: str | None) -> str | None:
        return self.ids.get(key) if key else None

    def finding(self, kind: str, key: str, message: str) -> None:
        self.out.findings.append({"kind": kind, "key": key, "message": message})

    def report(self, kind: str, key: str, message: str) -> None:
        self.out.reports.append({"kind": kind, "key": key, "message": message})

    def date(self, key: str, value):
        """A window for a frontmatter date value, or None (a finding says why, if there was a value)."""
        if value is None:
            return None
        window, problem = parse_date(value, self.calendar, self.ages, self.vault.config.circa_years)
        typo = isinstance(value, str) and value.split()[:1] and any(
            value.split()[0].upper() == a.abbrev.upper() != value.split()[0] for a in self.calendar.ages)
        if problem and window is None and not typo and ("in no age" in problem or "not an age of this calendar" in problem):
            self.report("out_of_calendar", key, f"{value!r}: {problem}")  # another age's canon: not this run's
        elif problem:
            self.finding("date" if window is None else "date_clamped", key, f"{value!r}: {problem}")
        return window

    def link(self, value, expects: set[str] | None = None) -> str | None:
        return self.vault.resolve(value, expects) if isinstance(value, str) else None

    def touches_run(self, window) -> bool:
        return window is not None and window[1] >= self.start and window[0] <= self.end

    def pin(self, p: Pin) -> Pin:
        self.out.pins.append(p)
        return p

    def order(self, before: Pin, after: Pin, key: str, what: str) -> None:
        """`before` comes before `after`: a pin when both touch the run, else checked here."""
        pid = f"{before.id}:before:{after.id}"
        if before.window and after.window and before.window[0] > after.window[1]:
            self.finding("infeasible_ordering", key, f"{what}: {before.id} can't come before {after.id}")
        elif self.touches_run(before.window) and self.touches_run(after.window):
            if not any(p.id == pid for p in self.out.pins):  # (A before: B and B after: A are one ordering)
                self.pin(Pin(pid, "ordering", payload={"before": before.id, "after": after.id}))
        elif before.window and after.window and before.window[1] < after.window[0]:
            self.report("ordering_met", key, f"{what}: {before.id} before {after.id} (outside the run; the dates agree)")
        else:
            self.report("ordering_undetermined", key, f"{what}: {before.id} before {after.id} (outside the run; "
                        "the windows overlap, so the order can't be told)")


def _events(ctx: Context) -> None:
    for key, note in ctx.notes("event"):
        eid = ctx.id_of(key)
        if eid is None:
            continue
        fm = note.frontmatter
        window = ctx.date(key, fm.get("date", fm.get("aat-event-start-date")))
        engine = fm.get("engine")
        if not engine:
            ctx.out.unmodelled.append({"id": eid, "key": key,
                                       "window": [d.to_json() for d in window] if window else None})
            continue
        if engine in ctx.owned:
            ctx.finding("birth_from_event" if engine == "people.birth" else "owned_event", key,
                        f"{engine} events come from the notes a hook reads (births: character notes), not event notes")
            continue
        if window is None:
            ctx.finding("undated_event", key, f"an {engine} event needs a date to be pinned")
            continue
        roles, ok = {}, True
        participants = fm.get("participants") or {}
        for r, value in sorted(participants.items() if isinstance(participants, dict) else []):
            members = []
            for v in value if isinstance(value, list) else [value]:
                cid = ctx.id_of(ctx.link(v))
                if cid is None:
                    ctx.finding("not_canon_participant", key, f"{r}: {v!r} is not a canon note with an id")
                    ok = False
                else:
                    members.append(cid)
            roles[r] = members
        if ok:
            ctx.anchors[key] = ctx.pin(Pin(f"{eid}:event", "event", window=window,
                                           payload={"type": engine, "roles": roles}))


def _orderings(ctx: Context) -> None:
    for key, note in ctx.vault.notes.items():
        if role(note) != "pin_source":
            continue
        for field_, earlier in (("after", True), ("before", False)):
            value = note.frontmatter.get(field_)
            for v in value if isinstance(value, list) else ([value] if value else []):
                other = ctx.link(v)
                a, b = (ctx.anchors.get(other), ctx.anchors.get(key))
                if not earlier:
                    a, b = b, a
                if a is None or b is None:
                    ctx.report("ordering_unanchored", key, f"{field_} {v}: one side has no event pin to order")
                    continue
                ctx.order(a, b, key, f"{field_} {v}")


def extract(vault, calendar, start: Date, end: Date, hooks=()) -> Extraction:
    """Every pin the vault's canon gives for a run from `start` to `end`, and what couldn't be pinned."""
    ctx = Context(vault, calendar, start, end, owned=frozenset().union(*(getattr(h, "owns", ()) for h in hooks)))
    _events(ctx)
    for hook in hooks:
        hook(ctx)
    _orderings(ctx)
    out = ctx.out
    out.pins.sort(key=lambda p: p.id)
    for lst in (out.findings, out.reports):
        lst.sort(key=lambda f: (f["key"], f["kind"], f["message"]))
    out.unmodelled.sort(key=lambda u: u["id"])
    out.expectations.sort(key=lambda e: (e["subject"], e["kind"]))
    out.placements = dict(sorted(out.placements.items()))
    return out
