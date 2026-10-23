"""Feasibility (S2 spec §8): can the vault's pins all hold in one run? Two passes, one vocabulary.

1. **S1's** `feasibility(pins, start, end)`: windows, scope, orderings and their cycles.
2. **Each hook's** `check(extraction, vault, races)`: what its world knows (the people hook checks
   lineages, lives, ages at a birth and reigns: `renasci.people.vault.people_check`).

Verdicts are S1's: `ok`, `out_of_scope`, `unsupported`, `infeasible`. The report names each pin's verdict,
why, and the notes involved; `feasible(extraction, report)` is the pins a run should be given (the
infeasible and unsupported ones dropped, before `apply_pins` ever sees them).
"""

from __future__ import annotations

from renasci.core.pins import feasibility as s1_feasibility


def check(extraction, vault, start, end, hooks=(), races=None, calendar=None) -> dict:
    """{"pins": {id: {verdict, why, notes}}, "findings": [...], "reports": [...]}."""
    owner = {}  # pin id -> the note key it came from (pin ids start with the note's id)
    by_id = {}
    for key, cid in _ids(vault).items():
        by_id[cid] = key
    for p in extraction.pins:
        head = p.id.split(":")[0] + ":" + p.id.split(":")[1]
        owner[p.id] = by_id.get(head)
    s1 = s1_feasibility(extraction.pins, start, end)
    pins = {p.id: {"verdict": s1[p.id], "why": "" if s1[p.id] == "ok" else f"S1: {s1[p.id]}",
                   "notes": [owner[p.id]] if owner.get(p.id) else []} for p in extraction.pins}
    out = {"pins": pins, "findings": [], "reports": []}
    for hook in hooks:
        hook_check = getattr(hook, "check", None)
        if hook_check is not None:
            hook_check(extraction, vault, races, out, calendar)
    out["findings"].sort(key=lambda f: (f.get("key") or "", f["kind"], f["message"]))
    out["reports"].sort(key=lambda f: (f.get("key") or "", f["kind"], f["message"]))
    out["pins"] = dict(sorted(out["pins"].items()))
    return out


def _ids(vault):
    from renasci.vault.ids import assign

    return assign(vault)


def infeasible(report: dict, pin_id: str, why: str, notes=()) -> None:
    """Mark a pin infeasible (a hook's check calls this), keeping the first reason and every note."""
    entry = report["pins"].get(pin_id)
    if entry is None:
        return
    if entry["verdict"] != "infeasible":
        entry["verdict"], entry["why"] = "infeasible", why
    entry["notes"] = sorted(set(entry["notes"]) | {n for n in notes if n})


def feasible(extraction, report: dict) -> list:
    """The pins a run should be given: those not infeasible or unsupported (out-of-scope pins are kept:
    S1 classifies them again and ignores them)."""
    return [p for p in extraction.pins if report["pins"][p.id]["verdict"] in ("ok", "out_of_scope")]
