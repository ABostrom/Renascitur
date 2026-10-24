"""The `renasci` command line.

    renasci run <recipe.toml> [--out runs]
    renasci replay <run-folder> --recipe <recipe.toml> [--from "1X 40"] [--out runs]
    renasci diff <baseline-run> <variant-run>      (exit 3 if anything is unexplained)
    renasci inspect <run-folder> (--event <id> | --entity <id>)
    renasci bench [--years 300] [--people 100] [--history bench/history.csv]
    renasci observe [runs] [--port 8765] [--allow-launch]   (the Observatory, on localhost)
    renasci latch <run-folder> [--top 10] [--launch N [--kind K] [--date D] [--until D] [--name N]] [--out runs]
    renasci stories <run-folder> [--top 10] [--from 20 --to 30]
    renasci vault check [docs] [--json]            (load the vault: notes, links, findings; read-only)

`run` writes a run folder with a checkpoint every N years. `replay` forks a run at the latest
checkpoint before the first changed ripple (or `--from`), restores, and continues with the new
recipe. `diff` explains every difference between two runs (no unexplained divergence). `latch` ranks
the run's latch points into `analysis/latch.json`; `--launch N` replays point N as a what-if and diffs it.
`stories` finds the run's arcs and sagas (`analysis/stories.json`); `--from/--to` lists what flows through
those years.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import gzip
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from renasci.analysis.divergence import analyse
from renasci.analysis.latch import latch_points
from renasci.analysis.stories import period, stories
from renasci.core.calendar import Date
from renasci.io.checkpoint import load_checkpoint, save_checkpoint
from renasci.io.recipe import load_recipe, parse_recipe
from renasci.io.runfolder import TABLES, RunFolder, cut, flush
from renasci.worlds import get_world


def _checkpoint_dates(start: Date, end: Date, every: int) -> list[Date]:
    return [Date(start.age, y, 0) for y in range(start.year + every, end.year + 1, every)]


def _finish(engine, folder: RunFolder, recipe, after: Date | None = None) -> None:
    """Run to the end, cutting a segment and saving a checkpoint at each checkpoint date."""
    (folder.path / "checkpoints").mkdir(exist_ok=True)
    for at in _checkpoint_dates(engine.start, recipe.end, recipe.checkpoint_every_years):
        if after is not None and at <= after:
            continue
        engine.run_before(at)
        index = cut(engine, folder, at)
        save_checkpoint(folder.path / "checkpoints" / f"{at.age}-{at.year}-{at.day}.json.gz",
                        engine.checkpoint(at=at, segments=index + 1))
    engine.run(until=recipe.end)
    flush(engine, folder)
    folder.close_segment()
    save_checkpoint(folder.path / "state.json.gz", engine.store.to_json())
    folder.manifest["meta"]["state_hash"] = engine.state_hash()
    folder.manifest["meta"]["complete"] = True  # written last: readers refuse folders without it
    folder.save_manifest()


def _open_complete(path) -> RunFolder:
    rf = RunFolder.open(path)
    if rf.manifest["meta"].get("complete") is not True:
        raise ValueError(f"{path} is not a complete run (it may have failed); remove it and run again")
    return rf


def cmd_run(args) -> int:
    _run(load_recipe(args.recipe), Path(args.out))
    return 0


def _cast(recipe, world) -> dict:
    """The canon a run is cast from (S2 §7): the vault's pins for the run's window, checked, with the casting
    input and log. Kept in the run folder as canon.json, so a replay uses exactly this."""
    from renasci.people.casting import canon_from, castable
    from renasci.people.races import Race
    from renasci.people.vault import people_hook
    from renasci.vault.feasibility import check, feasible
    from renasci.vault.loader import load
    from renasci.vault.pins import extract

    vault = load(recipe.vault["path"])
    scenario = world.scenario(**recipe.params)
    start, end = world.start(**recipe.params), recipe.end
    races = {r["id"]: Race.from_json(r) for r in scenario["races"]}
    found = extract(vault, world.calendar, start, end, hooks=[people_hook])
    report = check(found, vault, start, end, hooks=[people_hook], races=races, calendar=world.calendar)
    canon, log = canon_from(found, vault, scenario)
    pins, dropped = castable(feasible(found, report), scenario)
    return {"vault": recipe.vault["path"], "digest": vault.digest, "window": [start.to_json(), end.to_json()],
            "pins": [p.to_json() for p in pins], "dropped": dropped, "canon": canon, "casting": log,
            "feasibility": report, "findings": found.findings, "expectations": found.expectations}


def _write_canon(folder: Path, doc: dict) -> None:
    (folder / "canon.json").write_text(json.dumps(doc, indent=1, default=str), encoding="utf-8")
    (folder / "casting.json").write_text(json.dumps(doc["casting"], indent=1), encoding="utf-8")


def _write_geography(folder: Path, world, params: dict) -> None:
    """The geography a run used (S4 §3), for the Observatory: replays read routes from the checkpoint."""
    g = world.scenario(**params).get("geography") if world.scenario else None
    if isinstance(g, dict):
        from renasci import geo

        geo.save(folder / "geography.json", g)


def _run(recipe, out: Path, meta: dict | None = None, canon_doc: dict | None = None) -> Path:
    from renasci.core.pins import Pin

    world = get_world(recipe.world)
    if recipe.vault and canon_doc is None:
        canon_doc = _cast(recipe, world)
    extra = {}
    if canon_doc is not None:
        extra = {"pins": [Pin.from_json(p) for p in canon_doc["pins"]], "canon": canon_doc["canon"],
                 "end": recipe.end}  # pins past the run's end are out of scope, not guarded
    engine = world.new_engine(recipe.seed, ripples=recipe.ripples, **extra, **recipe.params)
    if recipe.reshuffles:
        engine.reshuffle(recipe.rng_reshuffles(world.calendar))
    engine.full_reads = recipe.full_reads
    folder = RunFolder.create(out / recipe.name, {"recipe": recipe.raw, "complete": False,
                                                  "calendar": world.calendar.to_json(), **(meta or {})})
    if canon_doc is not None:
        _write_canon(folder.path, canon_doc)
    _write_geography(folder.path, world, recipe.params)
    _finish(engine, folder, recipe)
    print(f"run {recipe.name}: {folder.manifest['segments']} segments, state {folder.manifest['meta']['state_hash']}")
    return folder.path


def cmd_replay(args) -> int:
    _replay(Path(args.run), load_recipe(args.recipe), Path(args.out), args.from_)
    return 0


def _replay(run: Path, new, out: Path, from_: str | None = None, rerun: bool = False, meta: dict | None = None) -> Path:
    """Fork `run` at the checkpoint before the first changed ripple (or `from_`) and finish it with `new`.
    With `rerun`, a change before the first checkpoint runs `new` from the start instead of refusing."""
    base = _open_complete(run)
    old = parse_recipe(base.manifest["meta"]["recipe"])
    world = get_world(new.world)

    def without_name_and_ripples(raw):  # full_reads only changes what is recorded, not what happens
        return {k: ({kk: vv for kk, vv in v.items() if kk not in ("name", "full_reads")} if k == "run" else v)
                for k, v in raw.items() if k not in ("ripple", "reshuffle")}

    if without_name_and_ripples(old.raw) != without_name_and_ripples(new.raw):
        raise ValueError("a replay may only change ripples, reshuffles, the run name and full_reads; "
                         "for anything else, `renasci run`")
    if from_:
        target = world.calendar.parse(from_)
    else:
        def key(r):
            return json.dumps(r.to_json(), sort_keys=True)

        before, after = {key(r) for r in old.ripples}, {key(r) for r in new.ripples}
        changed = [r.date for r in new.ripples if key(r) not in before]  # added or changed: new date
        changed += [r.date for r in old.ripples if key(r) not in after]  # removed or changed: old date
        changed += [d for d, _ in set(old.reshuffles) ^ set(new.reshuffles)]  # a reshuffle added or removed
        target = min(changed) if changed else new.end
    marks = [m for m in base.manifest["marks"] if Date.from_json(m["before"]) <= target]
    canon_doc = json.loads((base.path / "canon.json").read_text(encoding="utf-8")) \
        if (base.path / "canon.json").exists() else None
    if not marks and rerun:
        return _run(new, out, meta=meta, canon_doc=canon_doc)
    if not marks:
        raise ValueError(f"no checkpoint at or before {world.calendar.format(target)}; use `renasci run`")
    mark = marks[-1]
    at = Date.from_json(mark["before"])
    cp = load_checkpoint(base.path / "checkpoints" / f"{at.age}-{at.year}-{at.day}.json.gz")
    pins = []
    if canon_doc is not None:
        from renasci.core.pins import Pin

        pins = [Pin.from_json(p) for p in canon_doc["pins"]]
        if new.vault:
            from renasci.vault.loader import load

            try:
                changed = load(new.vault["path"]).digest != canon_doc["digest"]
            except FileNotFoundError:
                changed = False  # (the vault moved: canon.json is all a replay needs)
            if changed:
                print(f"note: the vault has changed since {base.path.name} was cast; the replay uses the canon it was "
                      "cast from (canon.json)")
    engine = world.restore(cp, new.seed, ripples=new.ripples, pins=pins,
                           reshuffles=new.rng_reshuffles(world.calendar), **new.params)
    engine.full_reads = new.full_reads
    folder = RunFolder.fork(base.path, out / new.name, keep=mark["segment"] + 1,
                            meta={"recipe": new.raw, "complete": False, "calendar": world.calendar.to_json(),
                                  "replayed_from": {"run": base.path.name, "at": mark["before"]}, **(meta or {})})
    if canon_doc is not None:
        _write_canon(folder.path, canon_doc)
    if (base.path / "geography.json").exists():  # the fork restores the base's routes, so it keeps its file
        shutil.copyfile(base.path / "geography.json", folder.path / "geography.json")
    _finish(engine, folder, new, after=at)
    print(f"replayed {new.name} from {base.path.name} at {world.calendar.format(at)}")
    return folder.path


def _load(path: Path) -> tuple[dict, dict, dict]:
    rf = _open_complete(path)
    tables = {t: list(rf.read(t)) for t in TABLES}
    state = json.loads(gzip.decompress((path / "state.json.gz").read_bytes()))
    ripples = {r["id"]: json.dumps(r, sort_keys=True) for r in rf.manifest["meta"]["recipe"].get("ripple", [])}
    return tables, state, ripples


def cmd_diff(args) -> int:
    return _diff(Path(args.a), Path(args.b))


def _reshuffled_since(a_path: Path, b_path: Path) -> list | None:
    """The earliest date from which one run's draws are re-rolled and the other's aren't (a reshuffle in
    one recipe but not the other): everything from then on differs on purpose."""
    raws = [_open_complete(p).manifest["meta"]["recipe"] for p in (a_path, b_path)]
    if not any(r.get("reshuffle") for r in raws):
        return None  # (no reshuffles: nothing to parse, so runs from older engines still compare)
    a, b = (parse_recipe(r) for r in raws)
    differ = set(a.reshuffles) ^ set(b.reshuffles)
    return min(d for d, _ in differ).to_json() if differ else None


def _diff(a_path: Path, b_path: Path) -> int:
    a, sa, ra = _load(a_path)
    b, sb, rb = _load(b_path)
    ripples = sorted({i for i in set(ra) | set(rb) if ra.get(i) != rb.get(i)})
    since = _reshuffled_since(a_path, b_path)
    report = {"runs": {"baseline": a_path.name, "variant": b_path.name},
              **analyse(a, b, sa, sb, ripples=ripples, since=since)}
    (b_path / "analysis").mkdir(exist_ok=True)
    (b_path / "analysis" / "divergence.json").write_text(json.dumps(report, separators=(",", ":")), encoding="utf-8")
    print(f"{report['divergent_events']} of {report['events']} events diverge; "
          f"{report['unexplained_events']} unexplained events, {report['unexplained_entities']} unexplained "
          f"entities, {report['unexplained_cells']} unexplained cells")
    if report["reads"] != "full":
        print(f"  note: reads were kept as digests ({report['reads']}), so this check is coarser; "
              "for the exact check, run both sides with full_reads = true")
    for e in report["unexplained"]["events"][:5]:
        print(f"  unexplained: {e['type']} {e['date']} {e['roles']}")
    clean = report["unexplained_events"] == report["unexplained_entities"] == report["unexplained_cells"] == 0
    return 0 if clean else 3  # 3, not 2: argparse uses 2 for usage errors


def cmd_latch(args) -> int:
    run = Path(args.run)
    rf = _open_complete(run)
    raw = rf.manifest["meta"]["recipe"]
    world = get_world(raw["run"]["world"])
    state = json.loads(gzip.decompress((run / "state.json.gz").read_bytes()))
    points = latch_points(list(rf.read("events")), list(rf.read("hinges")), state,
                          days_per_year=world.calendar.days_per_year)
    (run / "analysis").mkdir(exist_ok=True)
    (run / "analysis" / "latch.json").write_text(json.dumps({"run": run.name, "points": points}, indent=1),
                                                 encoding="utf-8")
    cal = world.calendar
    for p in points[:args.top]:
        r = p["ripple"]
        print(f"{p['rank']:>3}. {p['score']:7.3f}  {cal.format(Date.from_json(p['date']), 'day')}  {p['person']}  "
              f"{p['kind']}: {p['why']}  -> {r['kind']} ({p['means']})")
    if args.launch is None:
        return 0
    point = next((p for p in points if p["rank"] == args.launch), None)
    if point is None:
        raise ValueError(f"no latch point {args.launch} (there are {len(points)})")
    if raw.get("ripple"):
        raise ValueError("launch latch points from a run without ripples (a baseline)")
    ripple = _adjusted(point["ripple"], args, cal)
    out = Path(args.out)
    name = args.name or f"{raw['run']['name']}-latch{args.launch}"
    if not args.name:  # a second what-if of the same point gets its own folder
        n = 2
        while (out / name).exists():
            name, n = f"{raw['run']['name']}-latch{args.launch}-{n}", n + 1
    variant = json.loads(json.dumps(raw))
    variant["run"]["name"] = name
    variant["ripple"] = [{"id": f"latch{args.launch}", **ripple}]
    path = _replay(run, parse_recipe(variant), out, rerun=True,
                   meta={"latch_of": {"run": run.name, "rank": args.launch, "kind": point["kind"],
                                      "person": point["person"]}})
    code = _diff(run, path)
    if (run / "analysis" / "stories.json").exists():  # so the what-if's stories sit next to the baseline's
        found = stories(list(RunFolder.open(path).read("events")),
                        json.loads(gzip.decompress((path / "state.json.gz").read_bytes())))
        (path / "analysis" / "stories.json").write_text(json.dumps({"run": path.name, **found}, indent=1),
                                                        encoding="utf-8")
    print(f"latch: launched {path.name}")
    return code


def cmd_ripple(args) -> int:
    """Author one ripple on a run (#110): fork it before the ripple with its own recipe plus the ripple,
    then diff the new run against it. A branch of a branch keeps its parent's ripples."""
    run = Path(args.run)
    rf = _open_complete(run)
    raw = rf.manifest["meta"]["recipe"]
    cal = get_world(raw["run"]["world"]).calendar
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as e:
        raise ValueError(f"--params must be a JSON object: {e}") from None
    if not isinstance(params, dict):
        raise ValueError("--params must be a JSON object")
    state = json.loads(gzip.decompress((run / "state.json.gz").read_bytes()))
    known = {e["id"] for e in state["entities"]}
    geo_file = run / "geography.json"
    if geo_file.exists():  # (routes and places are entities too, but a fork restores its parent's file)
        g = json.loads(geo_file.read_text(encoding="utf-8"))
        known |= {x["id"] for k in ("routes", "places", "regions") for x in g.get(k, [])}
    if args.target not in known:
        raise ValueError(f"{args.target!r} isn't anyone or anything in {run.name}")
    have = raw.get("ripple", [])
    rid = f"{args.kind}{len(have) + 1}"
    while any(r["id"] == rid for r in have):
        rid += "x"
    out = Path(args.out)
    name = args.name or f"{raw['run']['name']}-{rid}"
    if not args.name:
        n = 2
        while (out / name).exists():
            name, n = f"{raw['run']['name']}-{rid}-{n}", n + 1
    elif (out / name).exists():  # (fail before any work; a failed attempt leaves its folder to be removed)
        raise ValueError(f"{out / name} already exists: pick another name, or remove that folder")
    variant = json.loads(json.dumps(raw))
    variant["run"]["name"] = name
    variant["ripple"] = [*have, {"id": rid, "kind": args.kind, "date": cal.format(cal.parse(args.date), "day"),
                                 "target": args.target, "params": params}]
    recipe = parse_recipe(variant)  # (checks the ripple's date and kind)
    from renasci.core.ripples import Ripple

    Ripple(rid, args.kind, cal.parse(args.date), args.target, params).check()  # (its params, before any work)
    path = _replay(run, recipe, out, rerun=True, meta={"ripple_of": {"run": run.name, "ripple": rid}})
    code = _diff(run, path)
    if (run / "analysis" / "stories.json").exists():  # (so its stories sit next to the parent's)
        found = stories(list(RunFolder.open(path).read("events")),
                        json.loads(gzip.decompress((path / "state.json.gz").read_bytes())))
        (path / "analysis" / "stories.json").write_text(json.dumps({"run": path.name, **found}, indent=1),
                                                        encoding="utf-8")
    print(f"ripple: launched {path.name}")
    return code


def _adjusted(r: dict, args, cal) -> dict:
    """The suggested ripple with any of --kind, --date, --until applied (dates as the calendar writes them)."""
    kind = args.kind or r["kind"]
    date = cal.parse(args.date) if args.date else Date.from_json(r["date"])
    out = {"kind": kind, "date": cal.format(date, "day"), "target": r["target"]}
    if kind == "protect":
        if args.until:  # a year means to its end
            until = cal.parse(args.until)
            if len(args.until.split()) == 2:
                until = Date(until.age, until.year, cal.days_per_year - 1)
        elif "until" in r["params"]:
            until = Date.from_json(r["params"]["until"])
        else:  # (a doom suggestion turned protect: ten years)
            until = Date(date.age, date.year + 10, cal.days_per_year - 1)
        if until < date:
            raise ValueError("--until is before the ripple's date")
        out["params"] = {"until": until.to_json()}
    return out


def cmd_pack(args) -> int:
    """A context pack (S12 §2, #115): one subject from one point of view, written to analysis/packs/ once
    it passes the pack schema."""
    from renasci.core.canon import canonical
    from renasci.story.pack import Run, build
    from renasci.story.schema import PACK, validate

    kinds = [_subject(args)]
    run = Run(args.run)
    pack = build(run, kinds[0], args.pov)
    findings = validate(pack, PACK)
    if findings:
        raise ValueError(f"the pack doesn't fit its schema: {findings[:3]}")
    out = run.folder / "analysis" / "packs" / f"{kinds[0][0]}-{_safe(kinds[0][1])}--{_safe(args.pov)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(pack) + "\n", encoding="utf-8", newline="\n")
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="replace")  # (not under a captured stdout)
    print(f"pack: {pack['subject']['title']} from {pack['pov']['name']}: {len(pack['events'])} events, "
          f"{len(pack['people'])} people, {len(pack['beliefs'])} beliefs -> {out}")
    return 0


def _subject(args) -> tuple[str, str]:
    kinds = [(k, getattr(args, k)) for k in ("arc", "saga", "person", "event", "topic") if getattr(args, k)]
    if len(kinds) != 1:
        raise ValueError("name one subject: --arc, --saga, --person, --event or --topic")
    return kinds[0]


def _safe(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-." else "_" for c in s)


def cmd_chronicle(args) -> int:
    """A POV chronicle (S12 §3, #116): a subject told as its author believes it, to analysis/chronicles/."""
    from renasci.story.chronicle import chronicle
    from renasci.story.pack import Run

    subject = _subject(args)
    run = Run(args.run)
    doc = chronicle(run, subject, args.pov)
    out = run.folder / "analysis" / "chronicles" / f"{subject[0]}-{_safe(subject[1])}--{_safe(args.pov)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc["text"], encoding="utf-8", newline="\n")
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="replace")
    print(f"chronicle: {doc['title']}: "
          f"{len(doc['divergence'])} departures from the truth -> {out}")
    return 0


def cmd_check_prose(args) -> int:
    """A canon check (S12 §4, #117): prose read into claims and judged against the run, from a point of
    view; the report to analysis/checks/<digest of the text>.json, the findings printed (contradictions first)."""
    from renasci.core.canon import canonical
    from renasci.story.check import MAX_TEXT, check, findings
    from renasci.story.pack import Run

    src = Path(args.file)
    if src.stat().st_size > MAX_TEXT:
        raise ValueError(f"{src.name} is over {MAX_TEXT // 1024} KB")
    run = Run(args.run)
    report = check(run, src.read_text(encoding="utf-8"), args.pov)
    out = run.folder / "analysis" / "checks" / f"{report['text']}--{_safe(args.pov)}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(canonical(report) + "\n", encoding="utf-8", newline="\n")
    getattr(sys.stdout, "reconfigure", lambda **_: None)(errors="replace")
    for f in findings(report):
        what = f"{f['pred']} {f['args']}: {f['verdict']}" if "pred" in f else f"{f['mention']!r}: {f['why']} " \
            f"({', '.join(c.get('name') or c['id'] for c in f['candidates'][:5])})"
        print(f"{f['finding']:>13}  #{f['n']}  {what}  [{', '.join(f.get('events') or [])}]")
    counts = ", ".join(f"{n} {k}" for k, n in report["counts"].items() if n)
    print(f"check: {counts or 'no claims found'} -> {out}")
    return 0


def cmd_mcp(args) -> int:
    """The MCP server over runs and the vault (S12 §5, #118), on stdio."""
    from renasci.mcp import serve

    serve(Path(args.runs).resolve(), Path(args.vault).resolve() if args.vault else None)
    return 0


def cmd_claims(args) -> int:
    """What the run's world believes, judged against what happened: analysis/claims.json (#106)."""
    from renasci.analysis.claims import claims_report

    run = Path(args.run)
    rf = _open_complete(run)
    state = json.loads(gzip.decompress((run / "state.json.gz").read_bytes()))
    geo = run / "geography.json"
    geography = json.loads(geo.read_text(encoding="utf-8")) if geo.exists() else None
    report = claims_report(list(rf.read("events")), state, geography)
    (run / "analysis").mkdir(exist_ok=True)
    (run / "analysis" / "claims.json").write_text(json.dumps({"run": run.name, **report}, indent=1), encoding="utf-8")
    sys.stdout.reconfigure(errors="replace")
    print(f"{sum(len(t['claims']) for t in report['topics'])} claims in {len(report['topics'])} topics")
    for t in report["topics"][:args.top]:
        most = t["claims"][0]
        print(f"  {t['about_name']}: {most['text']} ({most['truth']}, {most['holders']} hold it)")
    return 0


def cmd_stories(args) -> int:
    run = Path(args.run)
    rf = _open_complete(run)
    state = json.loads(gzip.decompress((run / "state.json.gz").read_bytes()))
    found = stories(list(rf.read("events")), state)
    (run / "analysis").mkdir(exist_ok=True)
    (run / "analysis" / "stories.json").write_text(json.dumps({"run": run.name, **found}, indent=1), encoding="utf-8")
    lo = args.from_ if args.from_ is not None else args.to
    hi = args.to if args.to is not None else lo
    if lo is not None and hi < lo:
        raise ValueError(f"--from {lo} is after --to {hi}")
    shown = found if lo is None else period(found, lo, hi)
    arcs = sorted(shown["arcs"], key=lambda a: (-a["salience"], a["id"]))
    print(f"{len(found['arcs'])} arcs, {len(found['sagas'])} sagas"
          + (f"; {len(shown['arcs'])} arcs and {len(shown['sagas'])} sagas in years {lo}-{hi}" if lo is not None else ""))
    for sg in shown["sagas"][:args.top]:
        print(f"  saga  {sg['span'][0]:>4}-{sg['span'][1]:<4} {len(sg['arcs']):>2} arcs  {sg['title']}")
    for a in arcs[:args.top]:
        print(f"  arc   {a['span'][0]:>4}-{a['span'][1]:<4} {a['outcome']:<16} {a['title']}")
    return 0


def _run_window(args):
    """(calendar, start, end, races) for a vault command's --world/--from/--to."""
    import importlib

    from renasci.people.races import Race

    cal = get_world(args.world).calendar
    start, end = cal.parse(args.from_), cal.parse(args.to)
    if len(args.to.split()) == 2:  # a year: to its end
        end = Date(end.age, end.year, cal.days_per_year - 1)
    module = importlib.import_module("renasci.renascita" if args.world == "fourth_age" else f"renasci.{args.world}")
    scenario = getattr(module, "SCENARIO", None)
    races = {r["id"]: Race.from_json(r) for r in scenario["races"]} if scenario else {}
    return cal, start, end, races


REPO = Path(__file__).resolve().parents[2]  # (the checkout: maps/ lives at its root)


def _refuse_unless_ignored(out: Path) -> None:
    """Traced map data may be written inside the repo only where git ignores it (the repo is public)."""
    if not (REPO / ".git").exists() or not out.is_relative_to(REPO):
        return
    import subprocess

    probe = out / "markers.json"
    try:
        ignored = subprocess.run(["git", "check-ignore", "-q", str(probe)], cwd=REPO).returncode == 0
    except FileNotFoundError:  # (no git: say so rather than risk it)
        raise ValueError("can't check that the output is git-ignored (no git): pass --maps outside the repo") from None
    if not ignored:
        raise ValueError(f"{out} isn't git-ignored: traced map data must stay private (use maps/<world>/private)")


def _point(text: str) -> tuple[int, int]:
    try:
        x, y = (int(v) for v in text.split(","))
    except ValueError:
        raise ValueError(f"a point is x,y in the image's pixels, got {text!r}") from None
    return x, y


def cmd_map(args) -> int:
    """The map tools (S5): `import` reads the private image into a world's private layers; `grid` makes the
    world's cell grid from the import; `check` and `bake` set the map against a geography file."""
    from renasci.io.recipe import check_run_name

    maps = Path(args.maps) if args.maps else REPO / "maps"
    private = (maps / check_run_name(args.world) / "private").resolve()
    _refuse_unless_ignored(private)
    if args.map_command in ("import", "grid"):
        try:
            import PIL  # noqa: F401
        except ImportError:
            raise ValueError("the map tools need Pillow: uv sync --extra map") from None
    if args.map_command == "import":
        from renasci.mapimport import import_map

        report = import_map(Path(args.image), private, water=[_point(w) for w in args.water],
                            marker=_point(args.marker), base_width=args.base_width, mask_width=args.mask_width,
                            marker_width=args.marker_width, force=args.force)
        w, h = report["source"]["size"]
        print(f"imported {report['source']['name']} ({w}x{h}) into {private}: {report['land']:.0%} land, "
              f"{report['markers']} markers (private: git-ignored)")
        return 0
    from renasci import mapgrid

    if args.map_command == "grid":
        import numpy as np
        from PIL import Image

        if (private / "grid.json").exists():
            raise ValueError(f"{private / 'grid.json'} exists: a grid is made once (a new scale is a regrid)")
        if args.miles_across <= 0:
            raise ValueError("--miles-across must be positive")
        if not (private / "import.json").exists():
            raise ValueError(f"no import in {private}: run `renasci map import` first")
        report = json.loads((private / "import.json").read_text(encoding="utf-8"))
        w, h = report["source"]["size"]
        land = np.asarray(Image.open(private / "mask.png").convert("L")) > 127
        g = mapgrid.new_grid(args.miles_across, h / w, land=land)
        (private / "grid.json").write_text(json.dumps(g, indent=1, sort_keys=True), encoding="utf-8")
        water = sum(1 for v in g["cells"].values() if v.get("terrain") == "water")
        print(f"grid: {g['cols']} x {g['rows']} cells of {g['miles']} miles, {water} water (private: git-ignored)")
        return 0
    from renasci import geo

    if not (private / "grid.json").exists():
        raise ValueError(f"no grid in {private}: run `renasci map grid` first")
    grid = json.loads((private / "grid.json").read_text(encoding="utf-8"))
    layout_file = private / "layout.json"
    layout = json.loads(layout_file.read_text(encoding="utf-8")) if layout_file.exists() else {}
    doc = geo.load(args.geography)
    if args.map_command == "check":
        findings = mapgrid.check(doc, grid, layout)
    else:
        baked, findings = mapgrid.bake(doc, grid, layout)
        if not any(f["severity"] == "error" for f in findings):
            changed = [r["id"] for r, s in zip(baked["routes"], doc["routes"]) if r["days"] != s["days"]]
            changed += [p["id"] for p, s in zip(baked["places"], doc["places"]) if p["region"] != s["region"]]
            print(f"bake: {len(changed)} changed{': ' + ', '.join(changed) if changed else ''}")
            if args.write:
                geo.save(args.geography, baked)
                print(f"wrote {args.geography}")
            elif changed:
                print("(a dry run: --write to save)")
    for f in findings:
        print(f"  {f['severity']}: {f['message']}")
    if not findings:
        print("map: ok")
    return 1 if any(f["severity"] == "error" for f in findings) else 0


def cmd_vault(args) -> int:
    from renasci.vault.loader import load

    vault = load(args.docs)
    if args.vault_command == "propose":
        from renasci.vault.proposals import propose, write_proposal

        run = Path(args.run)
        rf = _open_complete(run)
        state = json.loads(gzip.decompress((run / "state.json.gz").read_bytes()))
        cal = get_world(rf.manifest["meta"]["recipe"]["run"]["world"]).calendar
        bindings = {}
        for row in rf.read("pins"):  # canon ids born in the run, through their birth pins
            bindings.update(row.get("binding") or {})
        rel, text, notes = propose(state, list(rf.read("events")), args.entity, vault, cal,
                                   source={"run": run.name, "run_path": str(run.resolve()),
                                           "state_hash": rf.manifest["meta"].get("state_hash", "")},
                                   bindings=bindings, causes=args.cause)
        sys.stdout.reconfigure(errors="replace")
        for note in notes:
            print(f"note: {note}")
        if not args.write:
            print(f"would write {rel}:\n{text}\n(run again with --write to write it)")
            return 0
        written = write_proposal(args.docs, rel, text)
        if written != rel:
            print(f"note: {rel} is someone else's, or you've edited it: kept as it is")
        print(f"wrote {written} (canon: proposed; promote it by setting canon: true)")
        return 0
    if args.vault_command == "suggest":
        from renasci.vault.suggest import apply, suggest

        sys.stdout.reconfigure(errors="replace")
        found, skipped = suggest(vault)
        for key, fields in found.items():
            print(f"{key}.md")
            for k, v in fields.items():
                print(f'  +{k}: "{v}"')
        for sk in skipped:
            print(f"skipped {sk['key']}: {sk['field']}: {sk['why']}")
        if args.write:
            print(f"added fields to {apply(vault, found)} note(s); review the diff before committing")
        else:
            print(f"would add fields to {len(found)} note(s)" + ("; run again with --write to add them" if found else ""))
        return 0
    if args.vault_command == "stale":
        from renasci.vault.proposals import stale

        found = stale(args.docs, args.runs)
        for s in found:
            print(f"{s['path']}: {s['why']}")
        print(f"{len(found)} stale proposal(s); nothing was deleted" if found else "no stale proposals")
        return 0
    if args.vault_command == "pins":
        from renasci.people.vault import people_hook
        from renasci.vault.pins import extract

        cal, start, end, _ = _run_window(args)
        found = extract(vault, cal, start, end, hooks=[people_hook])
        sys.stdout.buffer.write(json.dumps(found.to_json(), ensure_ascii=False).encode("utf-8") + b"\n")
        sys.stdout.flush()
        return 0
    if args.vault_command == "ids":
        from renasci.vault.ids import migrate

        sys.stdout.reconfigure(errors="replace")
        plan = migrate(vault, write=args.write)
        for c in plan:
            print(f"{c['key']}.md")
            print(f"  +{c['line']}")
        verb = "added" if args.write else "would add"
        print(f"{verb} {len(plan)} id line(s)" + ("" if args.write or not plan else "; run again with --write to add them"))
        return 0
    found = report = None
    if args.world:  # the pins a run over --from..--to would get, and whether they can all hold
        from renasci.people.vault import people_hook
        from renasci.vault.feasibility import check
        from renasci.vault.pins import extract as extract_pins

        cal, start, end, races = _run_window(args)
        found = extract_pins(vault, cal, start, end, hooks=[people_hook])
        report = check(found, vault, start, end, hooks=[people_hook], races=races, calendar=cal)
    if args.json:  # UTF-8 whatever the console's code page (names like Yōkuro no Ki)
        data = vault.to_json()
        if report is not None:
            data |= {"extraction": found.to_json(), "feasibility": report}
        sys.stdout.buffer.write(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8") + b"\n")
        sys.stdout.flush()
        return 0
    sys.stdout.reconfigure(errors="replace")
    from renasci.vault.ids import check_ids, migrate
    from renasci.vault.mapping import role

    vault.findings = sorted(vault.findings + check_ids(vault), key=lambda f: (f["key"], f["line"], f["kind"]))
    missing = len(migrate(vault))
    counts: dict[str, int] = {}
    for f in vault.findings:
        counts[f["kind"]] = counts.get(f["kind"], 0) + 1
    sources: dict[str, int] = {}
    roles: dict[str, int] = {}
    for n in vault.notes.values():
        roles[role(n)] = roles.get(role(n), 0) + 1
        sources[n.type_from] = sources.get(n.type_from, 0) + 1
    print(f"{len(vault.notes)} notes, {len(vault.findings)} findings, digest {vault.digest[:12]}")
    print(f"  typed by frontmatter {sources.get('frontmatter', 0)}, by folder {sources.get('folder', 0)}, "
          f"untyped (essay) {sources.get('default', 0)}")
    print("  " + ", ".join(f"{n} {r.replace('_', ' ')}" for r, n in sorted(roles.items(), key=lambda x: -x[1])))
    if missing:
        print(f"  {missing} notes have no id yet (`renasci vault ids` lists them; --write adds them)")
    if report is not None:
        verdicts: dict[str, int] = {}
        for v in report["pins"].values():
            verdicts[v["verdict"]] = verdicts.get(v["verdict"], 0) + 1
        statuses: dict[str, int] = {}
        for pl in found.placements.values():
            statuses[pl["status"]] = statuses.get(pl["status"], 0) + 1
        print(f"  pins for {args.from_}..{args.to}: " + (", ".join(f"{n} {v}" for v, n in sorted(verdicts.items())) or "none"))
        print("  characters: " + (", ".join(f"{n} {s}" for s, n in sorted(statuses.items())) or "none"))
        lines = [f"  {v['verdict']}: {pid}: {v['why']}" for pid, v in report["pins"].items()
                 if v["verdict"] in ("infeasible", "unsupported")]
        lines += [f"  {f.get('key')}  {f['kind']}  {f['message']}"
                  for f in report["findings"] + found.findings + report["reports"] + found.reports]
        for line in lines[:args.top]:
            print(line)
        if len(lines) > args.top:
            print(f"  ... and {len(lines) - args.top} more about pins (--top N, or --json)")
    for kind, n in sorted(counts.items()):
        print(f"  {kind}: {n}")
    for f in vault.findings[:args.top]:
        print(f"  {f['key']}:{f['line']}  {f['kind']}  {f['message']}")
    if len(vault.findings) > args.top:
        print(f"  ... and {len(vault.findings) - args.top} more (--top N, or --json)")
    return 0


def cmd_inspect(args) -> int:
    path = Path(args.run)
    rf = _open_complete(path)
    if args.event:
        event = next((e for e in rf.read("events") if e["id"] == args.event), None)
        if event is None:
            raise ValueError(f"no event {args.event}")
        print(json.dumps(event, indent=1))
        causes = [c for c in rf.read("causes") if c["event"] == args.event]
        for c in causes:
            print(f"caused by {c['kind']} {c['ref']}")
    if args.entity:
        state = json.loads(gzip.decompress((path / "state.json.gz").read_bytes()))
        record = next((e for e in state["entities"] if e["id"] == args.entity), None)
        print(json.dumps(record, indent=1) if record else f"{args.entity}: not in the final state")
        ids = {p["event"] for p in rf.read("participants") if p["entity"] == args.entity}
        print("events:")
        for e in rf.read("events"):
            if e["id"] in ids:
                print(f"  {e['date']} {e['type']} {e['id']}")
        print("state changes:")
        for d in rf.read("state_deltas"):
            if d["entity"] == args.entity:
                print(f"  {d['date']} {d['field']}: {json.dumps(d['old'])} -> {json.dumps(d['new'])}  ({d['event']})")
    return 0


BENCH_FIELDS = ["date", "commit", "engine", "python", "numpy", "world", "years", "people_start", "people_peak",
                "events", "seconds", "years_per_s", "events_per_s", "run_mb"]


def cmd_bench(args) -> int:
    """Run a world for N years into a scratch run folder and append the numbers to the history: the toy
    world (`--people` per village) or the Fourth Age (`--scale` times the draft's population)."""
    from renasci.core.determinism import versions

    if args.years < 1 or args.people < 1 or args.scale < 1:
        raise ValueError("--years, --people and --scale must be at least 1")
    if args.world == "toy":
        from renasci.toy import CAL, START, new_engine

        engine = new_engine(seed=1234, people_per_village=args.people)
        label = f"toy x{args.people}"
    else:
        from renasci import renascita

        CAL, START = renascita.CAL, renascita.START
        last = CAL._by_index[START.age].last_year
        if last is not None and START.year + args.years - 1 > last:  # (past it, the scheduler drops everything)
            raise ValueError(f"the age ends in year {last}: at most {last - START.year + 1} years from "
                             f"{CAL.format(START)}")
        engine = renascita.new_engine(seed=1234, scale=args.scale)
        label = f"fourth_age x{args.scale}"
    out = Path(args.out)
    if out.exists():  # only ever delete a previous bench folder
        manifest = out / "manifest.json"
        is_bench = manifest.is_file() and json.loads(manifest.read_text(encoding="utf-8"))["meta"].get("bench") is True
        if not (out.is_dir() and (is_bench or not any(out.iterdir()))):
            raise FileExistsError(f"{out} exists and is not a previous bench run; choose another --out")
        shutil.rmtree(out)
    engine.full_reads = args.full_reads  # off by default, as in recipe runs (#151)
    folder = RunFolder.create(out, {"bench": True})
    people_start = peak = len(engine.store.ids("person", "active"))
    events = 0
    began = time.perf_counter()
    for year in range(1, args.years + 1):
        engine.run(until=Date(START.age, START.year + year - 1, CAL.days_per_year - 1))
        peak = max(peak, len(engine.store.ids("person", "active")))
        events += len(engine.events)
        flush(engine, folder)
        if year % 10 == 0:
            folder.close_segment()
    folder.close_segment()
    seconds = time.perf_counter() - began
    run_mb = sum(f.stat().st_size for f in out.rglob("*") if f.is_file()) / 1e6
    try:
        commit = subprocess.run(["git", "describe", "--always", "--dirty"], capture_output=True, text=True,
                                check=True, cwd=Path(__file__).parent).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unknown"
    v = versions()
    row = {"date": datetime.date.today().isoformat(), "commit": commit, "engine": v["engine"], "python": v["python"],
           "numpy": v["numpy"], "world": label + (" full reads" if args.full_reads else " digest reads"), "years": args.years, "people_start": people_start,
           "people_peak": peak, "events": events, "seconds": round(seconds, 2),
           "years_per_s": round(args.years / seconds, 3), "events_per_s": round(events / seconds, 1),
           "run_mb": round(run_mb, 3)}
    history = Path(args.history)
    history.parent.mkdir(parents=True, exist_ok=True)
    new_file = not history.exists() or history.stat().st_size == 0
    if not new_file:
        with history.open(encoding="utf-8", newline="") as f:
            header = next(csv.reader(f), [])
        if header != BENCH_FIELDS:
            raise ValueError(f"{history} has columns {header}, expected {BENCH_FIELDS}; start a new history file")
    with history.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=BENCH_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)
    print(f"{args.years} years, {events} events in {seconds:.1f}s: {row['years_per_s']} years/s, "
          f"{row['events_per_s']} events/s, {row['run_mb']} MB, peak {peak} people")
    return 0


def cmd_observe(args) -> int:
    from renasci.observe import serve

    maps = Path(args.maps) if args.maps else REPO / "maps"
    if args.edit_map:
        if not Path(args.edit_map).is_file():
            raise ValueError(f"no geography file {args.edit_map}")
        _refuse_unless_ignored((maps / Path(args.edit_map).stem / "private").resolve())
    serve(args.app, args.runs, port=args.port, open_browser=not args.no_browser, launch=args.allow_launch,
          recipes=args.recipes, vault=args.vault, edit_map=args.edit_map, maps=maps)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="renasci", description="The Renascitur History Engine")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="run a recipe into a run folder")
    p.add_argument("recipe")
    p.add_argument("--out", default="runs")
    p = sub.add_parser("replay", help="replay a run from a checkpoint with a (changed) recipe")
    p.add_argument("run")
    p.add_argument("--recipe", required=True)
    p.add_argument("--from", dest="from_", default=None)
    p.add_argument("--out", default="runs")
    p = sub.add_parser("diff", help="explain the differences between two runs")
    p.add_argument("a")
    p.add_argument("b")
    p = sub.add_parser("inspect", help="show an event or an entity")
    p.add_argument("run")
    target = p.add_mutually_exclusive_group(required=True)
    target.add_argument("--event")
    target.add_argument("--entity")
    p = sub.add_parser("latch", help="rank a run's latch points; --launch N replays one as a what-if and diffs it")
    p.add_argument("run")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--launch", type=int, default=None)
    p.add_argument("--kind", choices=("protect", "doom"), default=None, help="override the suggested ripple's kind")
    p.add_argument("--date", default=None, help="override its date, e.g. '1K 25'")
    p.add_argument("--until", default=None, help="for protect: until when, e.g. '1K 40'")
    p.add_argument("--name", default=None, help="the what-if's run name (default <run>-latch<N>)")
    p.add_argument("--out", default="runs")
    p = sub.add_parser("stories", help="find a run's arcs and sagas; --from/--to lists what flows through those years")
    p.add_argument("run")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--from", dest="from_", type=int, default=None)
    p.add_argument("--to", type=int, default=None)
    p = sub.add_parser("map", help="the map tools (S5): import the private Inkarnate image")
    msub = p.add_subparsers(dest="map_command", required=True)
    m = msub.add_parser("import", help="read the map image into maps/<world>/private/ (needs: uv sync --extra map; "
                                       "decoding the full map takes about 1 GB of memory)")
    m.add_argument("image")
    m.add_argument("--world", required=True)
    m.add_argument("--maps", default=None, help="the maps folder (default: the repo's maps/, git-ignored inside)")
    m.add_argument("--water", action="append", required=True, help="x,y of a water pixel (repeat for each sea colour)")
    m.add_argument("--marker", required=True, help="x,y of a pixel inside one settlement marker")
    m.add_argument("--base-width", type=int, default=4096, help="the editor's copy of the image, in pixels across")
    m.add_argument("--mask-width", type=int, default=1024, help="land/water, in pixels across")
    m.add_argument("--marker-width", type=int, default=8192,
                   help="the width markers are found at (raise it if icons are under ~12 px in the original)")
    m.add_argument("--force", action="store_true", help="replace an earlier import")
    m = msub.add_parser("grid", help="make the world's cell grid from its import (once; private)")
    m.add_argument("--world", required=True)
    m.add_argument("--maps", default=None)
    m.add_argument("--miles-across", type=float, required=True, help="how many miles the map is across (Q1)")
    for name, what in (("check", "check a geography against the world's map"),
                       ("bake", "write the map's route days and regions into a geography (a dry run unless --write)")):
        m = msub.add_parser(name, help=what)
        m.add_argument("--world", required=True)
        m.add_argument("--maps", default=None)
        m.add_argument("--geography", required=True, help="the geography file (e.g. src/renasci/renascita/pyrosia.json)")
        if name == "bake":
            m.add_argument("--write", action="store_true")
    p = sub.add_parser("vault", help="the vault bridge (S2): check")
    vsub = p.add_subparsers(dest="vault_command", required=True)
    v = vsub.add_parser("check", help="load the vault and report its notes and findings (read-only)")
    v.add_argument("docs", nargs="?", default="docs")
    v.add_argument("--json", action="store_true")
    v.add_argument("--top", type=int, default=40)
    v.add_argument("--world", default=None, help="also extract pins in this world's calendar and check them")
    v.add_argument("--from", dest="from_", default="4A 1")
    v.add_argument("--to", default="4A 256")
    v = vsub.add_parser("ids", help="add missing id: lines to notes (a dry run unless --write)")
    v.add_argument("docs", nargs="?", default="docs")
    v.add_argument("--write", action="store_true")
    v = vsub.add_parser("propose", help="propose a run's person or event as a canon: proposed note (a dry run unless --write)")
    v.add_argument("run")
    v.add_argument("entity")
    v.add_argument("docs", nargs="?", default="docs")
    v.add_argument("--write", action="store_true")
    v.add_argument("--cause", action="append", default=[],
                   help="an event's own cause to keep with it (kind:ref, as the run records it); repeatable")
    v = vsub.add_parser("suggest", help="frontmatter from labelled body bullets (a dry run unless --write)")
    v.add_argument("docs", nargs="?", default="docs")
    v.add_argument("--write", action="store_true")
    v = vsub.add_parser("stale", help="list untouched proposals whose run is gone or has been run again")
    v.add_argument("docs", nargs="?", default="docs")
    v.add_argument("--runs", default="runs")
    v = vsub.add_parser("pins", help="the pins the vault's canon gives for a run window, as JSON")
    v.add_argument("docs", nargs="?", default="docs")
    v.add_argument("--world", default="fourth_age", help="whose calendar dates are read in")
    v.add_argument("--from", dest="from_", default="4A 1")
    v.add_argument("--to", default="4A 256")
    from renasci.core.ripples import KINDS

    p = sub.add_parser("ripple", help="add one ripple to a run and replay it as a branch, diffed against the run")
    p.add_argument("run")
    p.add_argument("--kind", required=True, choices=KINDS)
    p.add_argument("--target", required=True, help="the entity (or route, or settlement) it acts on")
    p.add_argument("--date", required=True, help="when, as the calendar writes it (e.g. '4A 12')")
    p.add_argument("--params", help="the kind's params as JSON, e.g. {\"until\": [4, 20, 359]}")
    p.add_argument("--name", help="the branch's run name (default: <run>-<kind><n>)")
    p.add_argument("--out", default="runs")
    p = sub.add_parser("pack", help="a context pack: one subject from one point of view (analysis/packs/)")
    p.add_argument("run")
    for k in ("arc", "saga", "person", "event", "topic"):
        p.add_argument(f"--{k}", help=f"the subject: a {k} id")
    p.add_argument("--pov", default="omniscient", help="omniscient, or a person, house or settlement id")
    p = sub.add_parser("chronicle", help="a POV chronicle: a subject told as its author believes it "
                                          "(analysis/chronicles/)")
    p.add_argument("run")
    for k in ("arc", "saga", "person", "event", "topic"):
        p.add_argument(f"--{k}", help=f"the subject: a {k} id")
    p.add_argument("--pov", default="omniscient", help="omniscient, or a person, house or settlement id")
    p = sub.add_parser("check-prose", help="a canon check: prose read into claims and judged against a run "
                                            "(analysis/checks/)")
    p.add_argument("run")
    p.add_argument("file", help="the prose (Markdown; `claims` blocks are read exactly)")
    p.add_argument("--pov", default="omniscient", help="whose account it is: omniscient, or a person, house or settlement id")
    p = sub.add_parser("mcp", help="an MCP server over runs and the vault, on stdio (for Claude)")
    p.add_argument("--runs", default="runs")
    p.add_argument("--vault", default=None, help="the vault folder its vault tools read (read-only)")
    p = sub.add_parser("claims", help="what a run's world believes, judged against what happened "
                                       "(writes analysis/claims.json)")
    p.add_argument("run")
    p.add_argument("--top", type=int, default=5)
    p = sub.add_parser("observe", help="serve the Observatory and a runs folder, read-only, on localhost")
    p.add_argument("runs", nargs="?", default="runs")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--app", default=str(Path(__file__).resolve().parents[2] / "observatory" / "build"))
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--allow-launch", action="store_true",
                   help="let the Observatory launch runs, replays and what-ifs (each writes a new run folder)")
    p.add_argument("--recipes", default="recipes", help="the recipes the Observatory may launch (with --allow-launch)")
    p.add_argument("--vault", default=None,
                   help="a vault the Observatory may write proposed notes into (with --allow-launch; never by default)")
    p.add_argument("--edit-map", default=None,
                   help="a geography file to edit at /edit (S5), with its world's private layers in --maps")
    p.add_argument("--maps", default=None, help="the maps folder (default: the repo's maps/)")
    p = sub.add_parser("bench", help="time a world (simulation plus writing the run folder, "
                                      "not world setup) and append to the benchmark history")
    p.add_argument("--world", choices=("toy", "fourth_age"), default="toy")
    p.add_argument("--scale", type=int, default=10, help="fourth_age: times the draft's population (10: M1 scale)")
    p.add_argument("--years", type=int, default=300)
    p.add_argument("--people", type=int, default=100, help="people per village (6 villages)")
    p.add_argument("--history", default="bench/history.csv")
    p.add_argument("--full-reads", action="store_true", help="keep every read row, as an analysis run would")
    p.add_argument("--out", default="runs/_bench")
    args = parser.parse_args(argv)
    try:
        commands = {"run": cmd_run, "replay": cmd_replay, "diff": cmd_diff, "inspect": cmd_inspect, "bench": cmd_bench, "latch": cmd_latch, "stories": cmd_stories, "claims": cmd_claims, "pack": cmd_pack, "chronicle": cmd_chronicle, "check-prose": cmd_check_prose, "mcp": cmd_mcp, "ripple": cmd_ripple, "map": cmd_map, "vault": cmd_vault,
                    "observe": cmd_observe}
        return commands[args.command](args)
    except (ValueError, FileExistsError, FileNotFoundError) as err:
        print(f"renasci: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
